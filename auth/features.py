"""
Feature extraction for the login-risk and bot-detection models.

The single most common way an ML security control fails in production is
training/serving skew: the offline pipeline computes a feature one way, the
online path computes it slightly differently, and the model quietly scores
garbage. Everything here is therefore built around one rule - **there is
exactly one function that turns raw signals into a vector, and both training
and inference call it.** The synthetic generator in ``datasets.py`` emits the
same :class:`LoginAttempt` / :class:`BotSignals` structures the live path
builds, so the two cannot drift apart.

Feature order is pinned by ``LOGIN_FEATURES`` / ``BOT_FEATURES`` and asserted
against the persisted model at load time, so a reordering that would otherwise
silently corrupt every score fails loudly instead.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from . import geo

# ==============================================================================
# LOGIN RISK
# ==============================================================================

LOGIN_FEATURES: List[str] = [
    "log_velocity_kmh",        # log1p of implied ground speed since last login
    "log_distance_km",         # log1p of great-circle distance since last login
    "log_hours_since_last",    # log1p of hours since the previous login
    "impossible_travel",       # 1 when implied speed exceeds a jet's cruise
    "new_country",             # country never seen on this account
    "new_city",                # city never seen on this account
    "country_familiarity",     # share of past logins from this country
    "asn_familiarity",         # share of past logins from this network
    "device_familiarity",      # share of past logins from this device
    "new_device",              # device fingerprint never seen
    "hour_deviation",          # circular distance from the user's usual hour
    "is_hosting_asn",          # datacenter / cloud range
    "is_proxy",                # known VPN / proxy / Tor exit
    "geo_unresolved",          # lookup failed - absence of evidence is a signal
    "failed_attempts_1h",      # recent failures against this account
    "log_logins_24h",          # attempt volume in the last day
    "log_account_age_days",    # young accounts carry more risk
    "tz_mismatch",             # browser timezone disagrees with IP timezone
]

# Above this the journey is not merely unusual, it is physically impossible.
# Kept as a separate hard rule as well as a model feature - see score_login().
IMPOSSIBLE_SPEED_KMH = geo.IMPOSSIBLE_SPEED_KMH


@dataclass
class LoginEvent:
    """A past, successful login. The history the features are computed against."""

    timestamp: float = 0.0
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: str = ""
    country_code: str = ""
    asn: str = ""
    device_id: str = ""


@dataclass
class LoginAttempt:
    """Everything known about the sign-in being scored right now."""

    timestamp: float = 0.0
    location: geo.GeoLocation = field(default_factory=geo.GeoLocation)
    device_id: str = ""
    browser_timezone: str = ""
    account_age_days: float = 0.0
    failed_attempts_1h: int = 0
    logins_24h: int = 0
    history: List[LoginEvent] = field(default_factory=list)


def _circular_hour_distance(a: float, b: float) -> float:
    """Distance between two clock hours, wrapping at midnight (0..12)."""
    d = abs(a - b) % 24.0
    return min(d, 24.0 - d)


def _typical_hour(history: Sequence[LoginEvent]) -> Optional[float]:
    """The user's habitual login hour, averaged on the circle.

    A plain arithmetic mean is wrong here: someone who logs in at 23:00 and
    01:00 has a typical hour of midnight, not noon.
    """
    if not history:
        return None
    import datetime as _dt

    sin_sum = cos_sum = 0.0
    for ev in history:
        hour = _dt.datetime.fromtimestamp(ev.timestamp).hour + \
            _dt.datetime.fromtimestamp(ev.timestamp).minute / 60.0
        angle = 2 * math.pi * hour / 24.0
        sin_sum += math.sin(angle)
        cos_sum += math.cos(angle)
    if abs(sin_sum) < 1e-9 and abs(cos_sum) < 1e-9:
        return None
    mean_angle = math.atan2(sin_sum / len(history), cos_sum / len(history))
    return (mean_angle * 24.0 / (2 * math.pi)) % 24.0


def extract_login_features(attempt: LoginAttempt) -> Dict[str, float]:
    """Turn a sign-in attempt plus account history into the model's features.

    Returns a name->value mapping; :func:`login_vector` flattens it in the
    pinned order.
    """
    import datetime as _dt

    loc = attempt.location
    history = sorted(attempt.history, key=lambda e: e.timestamp)

    # ---- travel ----------------------------------------------------------
    distance_km = 0.0
    hours_since = 0.0
    velocity = 0.0
    impossible = 0.0

    prior_with_coords = [e for e in history if e.latitude is not None and e.longitude is not None]
    if prior_with_coords and loc.has_coords:
        last = prior_with_coords[-1]
        distance_km = geo.haversine_km(
            last.latitude, last.longitude, loc.latitude, loc.longitude
        )
        hours_since = max(0.0, (attempt.timestamp - last.timestamp) / 3600.0)
        velocity = geo.travel_velocity_kmh(distance_km, hours_since)
        impossible = 1.0 if velocity > IMPOSSIBLE_SPEED_KMH else 0.0
    elif history:
        hours_since = max(0.0, (attempt.timestamp - history[-1].timestamp) / 3600.0)

    # ---- familiarity -----------------------------------------------------
    n = len(history)
    if n:
        country_hits = sum(1 for e in history if e.country_code and e.country_code == loc.country_code)
        city_hits = sum(1 for e in history if e.city and e.city == loc.city)
        asn_hits = sum(1 for e in history if e.asn and e.asn == loc.asn)
        device_hits = sum(1 for e in history if e.device_id and e.device_id == attempt.device_id)
        country_fam = country_hits / n
        asn_fam = asn_hits / n
        device_fam = device_hits / n
        new_country = 1.0 if country_hits == 0 else 0.0
        new_city = 1.0 if city_hits == 0 else 0.0
        new_device = 1.0 if device_hits == 0 else 0.0
    else:
        # First ever login: nothing is "new" in a meaningful sense, and marking
        # everything new would make every genuine first sign-in look like an
        # account takeover. Neutral priors instead.
        country_fam = asn_fam = device_fam = 0.5
        new_country = new_city = new_device = 0.0

    # ---- temporal --------------------------------------------------------
    typical = _typical_hour(history)
    if typical is None:
        hour_dev = 0.0
    else:
        now_hour = (
            _dt.datetime.fromtimestamp(attempt.timestamp).hour
            + _dt.datetime.fromtimestamp(attempt.timestamp).minute / 60.0
        )
        hour_dev = _circular_hour_distance(now_hour, typical) / 12.0  # normalise 0..1

    # ---- network reputation ---------------------------------------------
    # A private/loopback address is local development, not a real signal; it is
    # reported as resolved so dev sign-ins do not sit permanently at high risk.
    geo_unresolved = 0.0 if (loc.resolved or loc.is_private) else 1.0

    tz_mismatch = 0.0
    if attempt.browser_timezone and loc.timezone and not loc.is_private:
        tz_mismatch = 0.0 if attempt.browser_timezone == loc.timezone else 1.0

    return {
        "log_velocity_kmh": math.log1p(max(0.0, velocity)),
        "log_distance_km": math.log1p(max(0.0, distance_km)),
        "log_hours_since_last": math.log1p(max(0.0, hours_since)),
        "impossible_travel": impossible,
        "new_country": new_country,
        "new_city": new_city,
        "country_familiarity": country_fam,
        "asn_familiarity": asn_fam,
        "device_familiarity": device_fam,
        "new_device": new_device,
        "hour_deviation": hour_dev,
        "is_hosting_asn": 1.0 if loc.is_hosting else 0.0,
        "is_proxy": 1.0 if loc.is_proxy else 0.0,
        "geo_unresolved": geo_unresolved,
        "failed_attempts_1h": float(min(attempt.failed_attempts_1h, 20)),
        "log_logins_24h": math.log1p(max(0, attempt.logins_24h)),
        "log_account_age_days": math.log1p(max(0.0, attempt.account_age_days)),
        "tz_mismatch": tz_mismatch,
    }


def login_vector(attempt: LoginAttempt) -> List[float]:
    """Feature vector in the pinned ``LOGIN_FEATURES`` order."""
    feats = extract_login_features(attempt)
    return [float(feats[name]) for name in LOGIN_FEATURES]


# ==============================================================================
# BOT DETECTION
# ==============================================================================

BOT_FEATURES: List[str] = [
    "webdriver_flag",          # navigator.webdriver
    "headless_ua",             # UA string self-identifies as headless
    "ua_entropy",              # normalised length/shape of the UA string
    "plugin_count",            # headless browsers usually report zero
    "language_count",          # automation often ships a single language
    "hardware_concurrency",
    "device_memory",
    "screen_plausible",        # viewport vs screen consistency
    "touch_ua_agreement",      # touch support agrees with the claimed platform
    "log_fill_time_ms",        # focus -> submit elapsed time
    "pointer_samples",         # how many pointer moves were seen
    "pointer_entropy",         # variance in movement direction
    "pointer_straightness",    # 1.0 = perfectly straight path
    "keystroke_count",
    "keystroke_iki_mean",      # mean inter-keystroke interval
    "keystroke_iki_cv",        # coefficient of variation of the intervals
    "paste_used",
    "honeypot_filled",         # hidden field that only a scraper would fill
    "no_interaction",          # submitted with no pointer and no keystrokes
]

# Strings that only an automated client sends. This drives a *hard block* in
# scoring.py, so it must contain nothing a real user could legitimately ship.
#
# Notably absent: "electron". Electron is a desktop application runtime, not an
# automation tool - VS Code, Slack, Discord and many finance desktop clients
# all embed it and put it in their user agent. Treating it as proof of
# automation would permanently lock out every user on an Electron-based
# browser or desktop wrapper, which is exactly the kind of silent, total
# false positive that is hardest to diagnose from a support ticket.
_HEADLESS_UA = re.compile(
    r"headless|phantomjs|slimerjs|puppeteer|playwright|selenium|"
    r"webdriver|scrapy|python-requests|curl/|wget/|httpclient|okhttp|go-http-client",
    re.I,
)


@dataclass
class BotSignals:
    """Client-side telemetry collected by the browser probe.

    Every field has a safe default so a probe that fails to report - scripts
    blocked, an old browser - produces a defined vector instead of an
    exception. Absence of telemetry is itself scored, via ``no_interaction``.
    """

    user_agent: str = ""
    webdriver: bool = False
    plugin_count: int = 0
    language_count: int = 0
    hardware_concurrency: int = 0
    device_memory: float = 0.0
    screen_width: int = 0
    screen_height: int = 0
    viewport_width: int = 0
    viewport_height: int = 0
    touch_points: int = 0
    fill_time_ms: float = 0.0
    pointer_samples: int = 0
    pointer_entropy: float = 0.0
    pointer_path_length: float = 0.0
    pointer_displacement: float = 0.0
    keystroke_count: int = 0
    keystroke_iki_mean: float = 0.0
    keystroke_iki_std: float = 0.0
    paste_used: bool = False
    honeypot_filled: bool = False

    @classmethod
    def from_payload(cls, data: Dict[str, Any]) -> "BotSignals":
        """Build from the probe's JSON, coercing types and ignoring extras.

        The payload arrives from the client and is therefore untrusted: every
        value is coerced and clamped, and unknown keys are dropped rather than
        set as attributes.
        """
        data = data or {}

        def num(key: str, default: float = 0.0, lo: float = 0.0, hi: float = 1e9) -> float:
            try:
                return max(lo, min(hi, float(data.get(key, default))))
            except (TypeError, ValueError):
                return default

        def flag(key: str) -> bool:
            return bool(data.get(key, False))

        return cls(
            user_agent=str(data.get("user_agent", ""))[:512],
            webdriver=flag("webdriver"),
            plugin_count=int(num("plugin_count", 0, 0, 200)),
            language_count=int(num("language_count", 0, 0, 50)),
            hardware_concurrency=int(num("hardware_concurrency", 0, 0, 256)),
            device_memory=num("device_memory", 0, 0, 1024),
            screen_width=int(num("screen_width", 0, 0, 32768)),
            screen_height=int(num("screen_height", 0, 0, 32768)),
            viewport_width=int(num("viewport_width", 0, 0, 32768)),
            viewport_height=int(num("viewport_height", 0, 0, 32768)),
            touch_points=int(num("touch_points", 0, 0, 32)),
            fill_time_ms=num("fill_time_ms", 0, 0, 3.6e6),
            pointer_samples=int(num("pointer_samples", 0, 0, 100000)),
            pointer_entropy=num("pointer_entropy", 0, 0, 100),
            pointer_path_length=num("pointer_path_length", 0, 0, 1e7),
            pointer_displacement=num("pointer_displacement", 0, 0, 1e7),
            keystroke_count=int(num("keystroke_count", 0, 0, 10000)),
            keystroke_iki_mean=num("keystroke_iki_mean", 0, 0, 60000),
            keystroke_iki_std=num("keystroke_iki_std", 0, 0, 60000),
            paste_used=flag("paste_used"),
            honeypot_filled=flag("honeypot_filled"),
        )


def extract_bot_features(sig: BotSignals) -> Dict[str, float]:
    """Turn browser telemetry into the bot model's features."""
    ua = sig.user_agent or ""

    # A real UA is a long string with several parenthesised tokens; automation
    # libraries send either something very short ("python-requests/2.31") or a
    # copy-pasted string missing the usual structure.
    ua_entropy = min(1.0, len(ua) / 160.0) * (1.0 if "(" in ua else 0.4)

    # Viewport must fit inside the screen, and neither may be zero. Headless
    # defaults (800x600 with an identical viewport) trip this.
    screen_plausible = 1.0
    if sig.screen_width <= 0 or sig.screen_height <= 0:
        screen_plausible = 0.0
    elif sig.viewport_width > sig.screen_width or sig.viewport_height > sig.screen_height:
        screen_plausible = 0.0
    elif sig.viewport_width == sig.screen_width and sig.viewport_height == sig.screen_height:
        # No browser chrome at all is characteristic of headless rendering.
        screen_plausible = 0.3

    # A UA claiming a phone should report touch points, and vice versa.
    claims_mobile = bool(re.search(r"android|iphone|ipad|mobile", ua, re.I))
    has_touch = sig.touch_points > 0
    touch_agreement = 1.0 if claims_mobile == has_touch else 0.0

    # Humans move the pointer along curved paths, so the traced path is longer
    # than the straight-line displacement. A ratio at 1.0 means a programmatic
    # jump straight to the target.
    if sig.pointer_displacement > 1.0 and sig.pointer_path_length > 0:
        straightness = min(1.0, sig.pointer_displacement / sig.pointer_path_length)
    else:
        straightness = 1.0 if sig.pointer_samples == 0 else 0.0

    # Typing rhythm: humans vary, replay scripts do not. Coefficient of
    # variation normalises the spread against the speed, so a fast human typist
    # is not mistaken for a bot.
    if sig.keystroke_count >= 3 and sig.keystroke_iki_mean > 0:
        iki_cv = min(3.0, sig.keystroke_iki_std / sig.keystroke_iki_mean)
    else:
        iki_cv = 0.0

    no_interaction = 1.0 if (sig.pointer_samples == 0 and sig.keystroke_count == 0) else 0.0

    return {
        "webdriver_flag": 1.0 if sig.webdriver else 0.0,
        "headless_ua": 1.0 if _HEADLESS_UA.search(ua) else 0.0,
        "ua_entropy": ua_entropy,
        "plugin_count": float(min(sig.plugin_count, 20)),
        "language_count": float(min(sig.language_count, 10)),
        "hardware_concurrency": float(min(sig.hardware_concurrency, 32)),
        "device_memory": float(min(sig.device_memory, 32)),
        "screen_plausible": screen_plausible,
        "touch_ua_agreement": touch_agreement,
        "log_fill_time_ms": math.log1p(max(0.0, sig.fill_time_ms)),
        "pointer_samples": float(min(sig.pointer_samples, 500)),
        "pointer_entropy": min(sig.pointer_entropy, 5.0),
        "pointer_straightness": straightness,
        "keystroke_count": float(min(sig.keystroke_count, 200)),
        "keystroke_iki_mean": min(sig.keystroke_iki_mean, 2000.0),
        "keystroke_iki_cv": iki_cv,
        "paste_used": 1.0 if sig.paste_used else 0.0,
        "honeypot_filled": 1.0 if sig.honeypot_filled else 0.0,
        "no_interaction": no_interaction,
    }


def bot_vector(sig: BotSignals) -> List[float]:
    """Feature vector in the pinned ``BOT_FEATURES`` order."""
    feats = extract_bot_features(sig)
    return [float(feats[name]) for name in BOT_FEATURES]
