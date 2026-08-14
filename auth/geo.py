"""
IP geolocation and great-circle geometry for the login risk pipeline.

The impossible-travel signal is only as good as the coordinates behind it, so
this module is deliberately conservative: every lookup is cached, every failure
degrades to a well-marked "unknown" location rather than a plausible-looking
guess, and private / loopback addresses are recognised so local development
does not manufacture fake travel events.

Accuracy caveat that the risk model has to live with: commercial IP-to-city
databases are roughly city-accurate at best and are frequently wrong by
hundreds of kilometres for mobile carriers, which route traffic through
regional gateways. A user on a phone can appear to jump between cities without
moving. That is why velocity is treated as a graded signal with a wide
uncertainty band rather than a binary trigger, and why the model also weighs
ASN and device familiarity instead of trusting coordinates alone.
"""

from __future__ import annotations

import ipaddress
import json
import math
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

EARTH_RADIUS_KM = 6371.0088

# Commercial aircraft cruise around 900 km/h; 1000 gives headroom for the
# tailwind case before a journey is called physically impossible.
IMPOSSIBLE_SPEED_KMH = 1000.0

# City-level IP geolocation is routinely off by this much, especially on mobile
# networks. Displacements under this are treated as noise, not travel.
GEO_UNCERTAINTY_KM = 60.0

_LOOKUP_TIMEOUT_S = 3.0
_CACHE_TTL_S = 24 * 3600

_cache: Dict[str, tuple] = {}
_cache_lock = threading.Lock()


@dataclass
class GeoLocation:
    """A resolved network location. ``resolved`` is False when lookup failed."""

    ip: str = ""
    resolved: bool = False
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: str = ""
    region: str = ""
    country: str = ""          # human readable
    country_code: str = ""     # ISO-3166 alpha-2
    timezone: str = ""
    asn: str = ""              # autonomous system number, e.g. "AS15169"
    org: str = ""              # network operator name
    is_private: bool = False   # RFC1918 / loopback
    is_hosting: bool = False   # datacenter / cloud range
    is_proxy: bool = False     # known VPN / proxy / Tor exit
    is_mobile: bool = False    # mobile carrier network

    @property
    def has_coords(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def label(self) -> str:
        """Short human-readable place name for the UI and audit log."""
        if self.is_private:
            return "Local network"
        parts = [p for p in (self.city, self.country_code) if p]
        return ", ".join(parts) if parts else "Unknown location"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GeoLocation":
        known = {k: v for k, v in (data or {}).items() if k in cls.__annotations__}
        return cls(**known)


def is_private_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_unspecified
    )


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two decimal-degree points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def travel_velocity_kmh(
    distance_km: float,
    hours_elapsed: float,
    uncertainty_km: float = GEO_UNCERTAINTY_KM,
    min_hours: float = 1.0 / 60.0,
) -> float:
    """Implied ground speed between two logins.

    Two corrections keep this from crying wolf:

    * ``uncertainty_km`` is subtracted from the distance, so a user sitting
      still while their carrier reassigns them to a gateway 40 km away reads as
      zero travel rather than a 2400 km/h teleport.

    * ``hours_elapsed`` is floored at one minute. Two logins in the same second
      would otherwise divide by ~0 and produce an infinite velocity for what is
      usually just a page refresh.
    """
    effective_km = max(0.0, distance_km - uncertainty_km)
    if effective_km <= 0:
        return 0.0
    return effective_km / max(hours_elapsed, min_hours)


def lookup(ip: str, *, timeout: float = _LOOKUP_TIMEOUT_S) -> GeoLocation:
    """Resolve *ip* to a location, cached for 24h.

    Uses ip-api.com, which needs no API key. Any failure - offline, rate
    limited, malformed response - returns an unresolved GeoLocation. The caller
    is expected to check ``resolved`` and treat unknown as its own risk state,
    because silently substituting a default location would let an attacker
    suppress the travel signal just by being unresolvable.
    """
    ip = (ip or "").strip()
    if not ip:
        return GeoLocation(ip="", resolved=False)

    if is_private_ip(ip):
        return GeoLocation(ip=ip, resolved=True, is_private=True, city="Local", country="Local")

    now = time.time()
    with _cache_lock:
        hit = _cache.get(ip)
        if hit and now - hit[0] < _CACHE_TTL_S:
            return hit[1]

    loc = GeoLocation(ip=ip, resolved=False)
    try:
        fields = "status,country,countryCode,region,regionName,city,lat,lon,timezone,isp,org,as,proxy,hosting,mobile"
        url = f"http://ip-api.com/json/{urllib.parse.quote(ip)}?fields={fields}"
        req = urllib.request.Request(url, headers={"User-Agent": "reverie-terminal/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if payload.get("status") == "success":
            loc = GeoLocation(
                ip=ip,
                resolved=True,
                latitude=payload.get("lat"),
                longitude=payload.get("lon"),
                city=payload.get("city") or "",
                region=payload.get("regionName") or "",
                country=payload.get("country") or "",
                country_code=payload.get("countryCode") or "",
                timezone=payload.get("timezone") or "",
                asn=(payload.get("as") or "").split(" ")[0],
                org=payload.get("org") or payload.get("isp") or "",
                is_hosting=bool(payload.get("hosting")),
                is_proxy=bool(payload.get("proxy")),
                is_mobile=bool(payload.get("mobile")),
            )
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, OSError):
        # Deliberately swallowed: a geolocation outage must not block sign-in.
        # The unresolved location is itself fed to the model as a signal.
        pass

    with _cache_lock:
        _cache[ip] = (now, loc)
    return loc


def client_ip_from_headers(headers: Dict[str, str], fallback: str = "") -> str:
    """Best-effort client IP from proxy headers.

    Only the *first* entry of X-Forwarded-For is taken, and only when the app is
    actually behind a proxy it trusts. XFF is client-controllable: anything
    downstream can append to it, so treating the last entry as authoritative -
    or trusting the header at all on a directly-exposed server - lets an
    attacker choose which country they appear to be in and defeat the entire
    travel model. Deployments that are not behind a trusted proxy should leave
    TRUST_PROXY_HEADERS unset and rely on the socket address.
    """
    if os.environ.get("TRUST_PROXY_HEADERS", "").lower() in ("1", "true", "yes"):
        lowered = {k.lower(): v for k, v in (headers or {}).items()}
        for key in ("x-forwarded-for", "x-real-ip", "cf-connecting-ip"):
            raw = lowered.get(key)
            if raw:
                candidate = raw.split(",")[0].strip()
                if candidate:
                    return candidate
    return fallback
