"""
Synthetic training data for the login-risk and bot-detection models.

**Read this before trusting a score.** There is no real labelled corpus of
sign-ins for this application, so the models here are trained on simulated
accounts. A model trained on synthetic data learns the *generator's*
assumptions, not real attacker behaviour. The numbers reported by ``train.py``
measure how well the model recovers the process below - they are emphatically
not an estimate of field accuracy against a live adversary.

What that buys is still worth having: a calibrated, inspectable prior that
encodes rules a security engineer would otherwise hand-tune, and which can be
retrained on real events the moment there are any. ``auth/store.py`` logs every
real sign-in in exactly the schema this generator emits, so retraining on
production data is a matter of swapping the source, not rewriting the pipeline.

Design rule that matters most: **the classes must overlap.** A generator where
attackers are trivially separable produces AUC ~1.0 and a model that has
learned nothing transferable. So legitimate users here also travel
internationally, also use VPNs, also buy new laptops and also log in at 3am -
and the hard cases are generated deliberately:

    * a business traveller landing in a new country on a *known* device after a
      flight-consistent gap  ->  legitimate
    * an attacker in a new country on an *unknown* device after an impossible
      gap                     ->  suspicious

Those two differ only in device familiarity and implied velocity, which forces
the model to combine features rather than latch onto "new country = bad".
Roughly a fifth of the generated sample sits in that ambiguous band.

Feature vectors are produced by running the *live* extractor in
``features.py`` over simulated ``LoginAttempt`` objects, so the training path
cannot drift from the serving path.
"""

from __future__ import annotations

import math
import random
import time
from typing import Dict, List, Tuple

from . import geo
from .features import (
    BotSignals,
    LoginAttempt,
    LoginEvent,
    bot_vector,
    login_vector,
)

# Real coordinates so simulated journeys have realistic distances - the whole
# travel signal is meaningless with made-up geography.
CITIES: List[Tuple[str, str, float, float, str]] = [
    # (city, country_code, lat, lon, tz)
    ("London", "GB", 51.5074, -0.1278, "Europe/London"),
    ("Manchester", "GB", 53.4808, -2.2426, "Europe/London"),
    ("Dublin", "IE", 53.3498, -6.2603, "Europe/Dublin"),
    ("Paris", "FR", 48.8566, 2.3522, "Europe/Paris"),
    ("Berlin", "DE", 52.5200, 13.4050, "Europe/Berlin"),
    ("Frankfurt", "DE", 50.1109, 8.6821, "Europe/Berlin"),
    ("Amsterdam", "NL", 52.3676, 4.9041, "Europe/Amsterdam"),
    ("Madrid", "ES", 40.4168, -3.7038, "Europe/Madrid"),
    ("Milan", "IT", 45.4642, 9.1900, "Europe/Rome"),
    ("Zurich", "CH", 47.3769, 8.5417, "Europe/Zurich"),
    ("Stockholm", "SE", 59.3293, 18.0686, "Europe/Stockholm"),
    ("Warsaw", "PL", 52.2297, 21.0122, "Europe/Warsaw"),
    ("Lisbon", "PT", 38.7223, -9.1393, "Europe/Lisbon"),
    ("New York", "US", 40.7128, -74.0060, "America/New_York"),
    ("Boston", "US", 42.3601, -71.0589, "America/New_York"),
    ("Chicago", "US", 41.8781, -87.6298, "America/Chicago"),
    ("Austin", "US", 30.2672, -97.7431, "America/Chicago"),
    ("Denver", "US", 39.7392, -104.9903, "America/Denver"),
    ("San Francisco", "US", 37.7749, -122.4194, "America/Los_Angeles"),
    ("Seattle", "US", 47.6062, -122.3321, "America/Los_Angeles"),
    ("Los Angeles", "US", 34.0522, -118.2437, "America/Los_Angeles"),
    ("Miami", "US", 25.7617, -80.1918, "America/New_York"),
    ("Toronto", "CA", 43.6532, -79.3832, "America/Toronto"),
    ("Vancouver", "CA", 49.2827, -123.1207, "America/Vancouver"),
    ("Mexico City", "MX", 19.4326, -99.1332, "America/Mexico_City"),
    ("Sao Paulo", "BR", -23.5505, -46.6333, "America/Sao_Paulo"),
    ("Buenos Aires", "AR", -34.6037, -58.3816, "America/Argentina/Buenos_Aires"),
    ("Lagos", "NG", 6.5244, 3.3792, "Africa/Lagos"),
    ("Johannesburg", "ZA", -26.2041, 28.0473, "Africa/Johannesburg"),
    ("Cairo", "EG", 30.0444, 31.2357, "Africa/Cairo"),
    ("Dubai", "AE", 25.2048, 55.2708, "Asia/Dubai"),
    ("Tel Aviv", "IL", 32.0853, 34.7818, "Asia/Jerusalem"),
    ("Mumbai", "IN", 19.0760, 72.8777, "Asia/Kolkata"),
    ("Bengaluru", "IN", 12.9716, 77.5946, "Asia/Kolkata"),
    ("Singapore", "SG", 1.3521, 103.8198, "Asia/Singapore"),
    ("Hong Kong", "HK", 22.3193, 114.1694, "Asia/Hong_Kong"),
    ("Tokyo", "JP", 35.6762, 139.6503, "Asia/Tokyo"),
    ("Seoul", "KR", 37.5665, 126.9780, "Asia/Seoul"),
    ("Sydney", "AU", -33.8688, 151.2093, "Australia/Sydney"),
    ("Auckland", "NZ", -36.8485, 174.7633, "Pacific/Auckland"),
]

# Residential/broadband networks a legitimate user plausibly signs in from.
RESIDENTIAL_ASNS = [f"AS{n}" for n in (5089, 2856, 3320, 3215, 6830, 12876, 701, 7922, 6167)]
# Cloud and bulletproof-hosting ranges: normal for a scraper, unusual for a human.
HOSTING_ASNS = [f"AS{n}" for n in (14061, 16509, 15169, 24940, 20473, 63949, 9009)]

SECONDS_PER_DAY = 86400.0
CRUISE_KMH = 850.0  # used to decide whether a journey had time to happen


def _city_to_location(city: Tuple, asn: str, *, hosting=False, proxy=False, mobile=False) -> geo.GeoLocation:
    name, cc, lat, lon, tz = city
    return geo.GeoLocation(
        ip="simulated",
        resolved=True,
        latitude=lat,
        longitude=lon,
        city=name,
        country_code=cc,
        country=cc,
        timezone=tz,
        asn=asn,
        is_hosting=hosting,
        is_proxy=proxy,
        is_mobile=mobile,
    )


def _jitter_city(city: Tuple, rng: random.Random, km: float = 25.0) -> Tuple:
    """Nudge coordinates a little so repeat logins are not pixel-identical."""
    name, cc, lat, lon, tz = city
    dlat = rng.uniform(-km, km) / 111.0
    dlon = rng.uniform(-km, km) / (111.0 * max(0.2, math.cos(math.radians(lat))))
    return (name, cc, lat + dlat, lon + dlon, tz)


def _flight_hours(a: Tuple, b: Tuple) -> float:
    """Roughly how long the journey between two cities takes, door to door."""
    d = geo.haversine_km(a[2], a[3], b[2], b[3])
    return d / CRUISE_KMH + 3.0  # + airport overhead


def _build_history(rng: random.Random, home: Tuple, asn: str, device: str,
                   habitual_hour: float, count: int, end_ts: float) -> List[LoginEvent]:
    """A believable back-history of routine logins from the account's home."""
    events: List[LoginEvent] = []
    ts = end_ts - count * rng.uniform(0.6, 2.2) * SECONDS_PER_DAY
    for _ in range(count):
        ts += rng.uniform(0.4, 2.0) * SECONDS_PER_DAY
        # Land the timestamp near the habitual hour on its day.
        day_start = ts - (ts % SECONDS_PER_DAY)
        hour = (habitual_hour + rng.gauss(0, 1.6)) % 24.0
        stamp = day_start + hour * 3600.0
        c = _jitter_city(home, rng)
        events.append(LoginEvent(
            timestamp=stamp,
            latitude=c[2], longitude=c[3], city=c[0], country_code=c[1],
            asn=asn if rng.random() > 0.12 else rng.choice(RESIDENTIAL_ASNS),
            device_id=device if rng.random() > 0.15 else f"{device}-alt",
        ))
    return sorted(events, key=lambda e: e.timestamp)


def generate_login_dataset(n_accounts: int = 2600, seed: int = 20260814
                           ) -> Tuple[List[List[float]], List[int], List[str]]:
    """Simulate accounts and return ``(X, y, scenarios)``.

    Each account contributes one scored attempt. ``scenarios`` names the
    generating scenario per sample, so training can report where the residual
    errors actually land instead of only an aggregate score. Scenario mix is
    chosen to keep the ambiguous band well populated - see the module docstring.
    """
    rng = random.Random(seed)
    X: List[List[float]] = []
    y: List[int] = []
    scenarios: List[str] = []

    now = time.time()

    for _ in range(n_accounts):
        home = rng.choice(CITIES)
        home_asn = rng.choice(RESIDENTIAL_ASNS)
        device = f"dev-{rng.randrange(10**8)}"
        habitual_hour = rng.uniform(6.5, 22.0)
        account_age = rng.uniform(3, 1800)
        hist_len = rng.randint(3, 60)

        last_ts = now - rng.uniform(1.0, 96.0) * 3600.0
        history = _build_history(rng, home, home_asn, device, habitual_hour, hist_len, last_ts)
        if not history:
            continue
        prev = history[-1]

        roll = rng.random()

        # ---------------- legitimate scenarios (label 0) -------------------
        if roll < 0.24:
            scenario = "legit_home"
            c = _jitter_city(home, rng)
            loc = _city_to_location(c, home_asn, mobile=rng.random() < 0.3)
            ts = prev.timestamp + rng.uniform(0.5, 60.0) * 3600.0
            dev, label = device, 0
            failed, logins24 = rng.choice([0, 0, 0, 1]), rng.randint(1, 4)

        elif roll < 0.34:
            # Business travel: new country, but the gap allows the flight and
            # the device is the user's own. This is the case a naive
            # "new country = suspicious" rule gets wrong.
            scenario = "legit_travel_known_device"
            dest = rng.choice([c for c in CITIES if c[1] != home[1]])
            ts = prev.timestamp + _flight_hours(home, dest) * rng.uniform(1.05, 2.4) * 3600.0
            loc = _city_to_location(_jitter_city(dest, rng), rng.choice(RESIDENTIAL_ASNS),
                                    mobile=rng.random() < 0.5)
            dev, label = device, 0
            failed, logins24 = rng.randint(0, 2), rng.randint(1, 3)

        elif roll < 0.41:
            # Same city, brand new laptop. Novel device, everything else normal.
            scenario = "legit_new_device"
            c = _jitter_city(home, rng)
            loc = _city_to_location(c, home_asn)
            ts = prev.timestamp + rng.uniform(1.0, 72.0) * 3600.0
            dev, label = f"dev-{rng.randrange(10**8)}", 0
            failed, logins24 = rng.randint(0, 3), rng.randint(1, 4)

        elif roll < 0.47:
            # Corporate VPN / privacy VPN in the home country: proxy flag set,
            # known device, plausible hour. Legitimate but superficially shady.
            scenario = "legit_vpn"
            same_country = [c for c in CITIES if c[1] == home[1]] or [home]
            c = rng.choice(same_country)
            loc = _city_to_location(_jitter_city(c, rng), rng.choice(HOSTING_ASNS),
                                    hosting=True, proxy=rng.random() < 0.7)
            ts = prev.timestamp + rng.uniform(1.0, 48.0) * 3600.0
            dev, label = device, 0
            failed, logins24 = rng.randint(0, 2), rng.randint(1, 5)

        elif roll < 0.51:
            # Shift worker / insomniac: far off the habitual hour, nothing else
            # unusual. Stops the model treating odd hours as sufficient.
            scenario = "legit_odd_hour"
            c = _jitter_city(home, rng)
            loc = _city_to_location(c, home_asn)
            base = prev.timestamp + rng.uniform(6.0, 40.0) * 3600.0
            day_start = base - (base % SECONDS_PER_DAY)
            ts = day_start + ((habitual_hour + rng.uniform(9, 15)) % 24.0) * 3600.0
            dev, label = device, 0
            failed, logins24 = rng.randint(0, 2), rng.randint(1, 3)

        elif roll < 0.56:
            # Forgotten password: a burst of failures from the user's own
            # machine at home. Without this the model learns "failures ==
            # attack", and locks people out on the day they fumble a typo.
            scenario = "legit_fumbled_password"
            c = _jitter_city(home, rng)
            loc = _city_to_location(c, home_asn, mobile=rng.random() < 0.4)
            ts = prev.timestamp + rng.uniform(0.2, 40.0) * 3600.0
            dev, label = device, 0
            failed, logins24 = rng.randint(3, 12), rng.randint(4, 18)

        elif roll < 0.62:
            # Bought a laptop while abroad: new country, new device, and a
            # browser timezone that has not caught up. Ambiguous by design -
            # this is close to indistinguishable from a takeover, and some of
            # these *should* be misclassified.
            scenario = "legit_travel_new_device"
            dest = rng.choice([c for c in CITIES if c[1] != home[1]])
            ts = prev.timestamp + _flight_hours(home, dest) * rng.uniform(1.05, 3.0) * 3600.0
            loc = _city_to_location(_jitter_city(dest, rng), rng.choice(RESIDENTIAL_ASNS),
                                    mobile=rng.random() < 0.4)
            dev, label = f"dev-{rng.randrange(10**8)}", 0
            failed, logins24 = rng.randint(0, 4), rng.randint(1, 6)

        # ---------------- suspicious scenarios (label 1) -------------------
        elif roll < 0.71:
            # Account takeover: distant geography, unknown device, and a gap far
            # too short for the journey.
            scenario = "attack_impossible_travel"
            far = [c for c in CITIES
                   if geo.haversine_km(home[2], home[3], c[2], c[3]) > 4000]
            dest = rng.choice(far) if far else rng.choice(CITIES)
            ts = prev.timestamp + rng.uniform(0.08, 1.4) * 3600.0
            loc = _city_to_location(_jitter_city(dest, rng), rng.choice(RESIDENTIAL_ASNS + HOSTING_ASNS))
            dev, label = f"dev-{rng.randrange(10**8)}", 1
            failed, logins24 = rng.randint(0, 3), rng.randint(2, 12)

        elif roll < 0.79:
            # Credential stuffing: cloud host, throwaway device, repeated
            # failures, high attempt volume.
            scenario = "attack_credential_stuffing"
            dest = rng.choice(CITIES)
            loc = _city_to_location(_jitter_city(dest, rng), rng.choice(HOSTING_ASNS),
                                    hosting=True, proxy=rng.random() < 0.5)
            ts = prev.timestamp + rng.uniform(0.05, 20.0) * 3600.0
            dev, label = f"dev-{rng.randrange(10**8)}", 1
            failed, logins24 = rng.randint(4, 18), rng.randint(8, 40)

        elif roll < 0.86:
            # Slow, careful takeover from another continent - no impossible
            # velocity, so the model has to rely on device/ASN/hour novelty.
            scenario = "attack_distant_patient"
            far = [c for c in CITIES
                   if geo.haversine_km(home[2], home[3], c[2], c[3]) > 5000]
            dest = rng.choice(far) if far else rng.choice(CITIES)
            ts = prev.timestamp + rng.uniform(20.0, 90.0) * 3600.0
            loc = _city_to_location(_jitter_city(dest, rng), rng.choice(HOSTING_ASNS),
                                    hosting=rng.random() < 0.7, proxy=rng.random() < 0.6)
            dev, label = f"dev-{rng.randrange(10**8)}", 1
            failed, logins24 = rng.randint(0, 5), rng.randint(1, 8)

        elif roll < 0.91:
            # Proxy rotation: geolocation fails or resolves to a Tor exit.
            scenario = "attack_proxy_rotation"
            dest = rng.choice(CITIES)
            unresolved = rng.random() < 0.45
            loc = _city_to_location(_jitter_city(dest, rng), rng.choice(HOSTING_ASNS),
                                    hosting=True, proxy=True)
            if unresolved:
                loc = geo.GeoLocation(ip="simulated", resolved=False)
            ts = prev.timestamp + rng.uniform(0.1, 30.0) * 3600.0
            dev, label = f"dev-{rng.randrange(10**8)}", 1
            failed, logins24 = rng.randint(2, 14), rng.randint(3, 25)

        elif roll < 0.96:
            # Residential-proxy takeover. The current generation of ATO tooling
            # rents residential IP pools precisely to defeat ASN reputation, so
            # this one is quiet across every network signal: no hosting flag, no
            # proxy flag, few failures, matched timezone, a nearby city. All the
            # model has is device novelty plus a modest geographic shift.
            scenario = "attack_residential_stealth"
            near = [c for c in CITIES
                    if 200 < geo.haversine_km(home[2], home[3], c[2], c[3]) < 3000] or CITIES
            dest = rng.choice(near)
            ts = prev.timestamp + rng.uniform(6.0, 70.0) * 3600.0
            loc = _city_to_location(_jitter_city(dest, rng), rng.choice(RESIDENTIAL_ASNS),
                                    mobile=rng.random() < 0.35)
            dev, label = f"dev-{rng.randrange(10**8)}", 1
            failed, logins24 = rng.randint(0, 2), rng.randint(1, 5)

        else:
            # Session/fingerprint theft by infostealer malware: the attacker
            # replays the victim's own device fingerprint, so device
            # familiarity - the single strongest feature - points the wrong
            # way. Only the geography betrays it.
            scenario = "attack_stolen_fingerprint"
            far = [c for c in CITIES
                   if geo.haversine_km(home[2], home[3], c[2], c[3]) > 3000]
            dest = rng.choice(far) if far else rng.choice(CITIES)
            ts = prev.timestamp + rng.uniform(0.2, 10.0) * 3600.0
            loc = _city_to_location(_jitter_city(dest, rng),
                                    rng.choice(HOSTING_ASNS + RESIDENTIAL_ASNS),
                                    hosting=rng.random() < 0.4)
            dev, label = device, 1          # the victim's real device id
            failed, logins24 = rng.randint(0, 3), rng.randint(2, 10)

        # Browser timezone. Legitimate users usually match where they are, but
        # not always - a laptop that has not resynced after a flight will not.
        # Attackers usually do not bother, but the better tooling spoofs it.
        if label == 0:
            browser_tz = loc.timezone if rng.random() < 0.88 else rng.choice([c[4] for c in CITIES])
        else:
            browser_tz = rng.choice([c[4] for c in CITIES]) if rng.random() < 0.62 else loc.timezone

        # Ground truth in account security is itself uncertain: a login flagged
        # as takeover is sometimes later confirmed as the user, and a quiet
        # compromise can go unlabelled for months. A few percent of flipped
        # labels keeps the model from fitting the generator perfectly and keeps
        # the reported metrics in a believable range.
        if rng.random() < 0.03:
            label = 1 - label
            scenario += "_mislabelled"

        attempt = LoginAttempt(
            timestamp=ts,
            location=loc,
            device_id=dev,
            browser_timezone=browser_tz,
            account_age_days=account_age,
            failed_attempts_1h=failed,
            logins_24h=logins24,
            history=history,
        )
        X.append(login_vector(attempt))
        y.append(label)
        scenarios.append(scenario)

    return X, y, scenarios


# ==============================================================================
# BOT DETECTION
# ==============================================================================


def _human_signals(rng: random.Random) -> BotSignals:
    """A person filling in a login form."""
    mobile = rng.random() < 0.32
    if mobile:
        ua = rng.choice([
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
        ])
        sw, sh = rng.choice([(390, 844), (412, 915), (393, 852)])
        vw, vh = sw, sh - rng.randint(90, 160)
        touch = rng.randint(1, 5)
        cores = rng.choice([4, 6, 8])
        mem = rng.choice([3, 4, 6, 8])
    else:
        ua = rng.choice([
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
        ])
        sw, sh = rng.choice([(2560, 1440), (1920, 1080), (1512, 982), (3440, 1440)])
        vw, vh = sw - rng.randint(0, 400), sh - rng.randint(120, 300)
        touch = 0
        cores = rng.choice([4, 8, 10, 12, 16])
        mem = rng.choice([8, 16, 32])

    # Humans arc toward a target, so the traced path exceeds the displacement.
    displacement = rng.uniform(250, 1400)
    path = displacement * rng.uniform(1.35, 3.4)
    n_keys = rng.randint(10, 34)
    iki_mean = rng.uniform(80, 260)

    sig = BotSignals(
        user_agent=ua,
        webdriver=False,
        plugin_count=rng.randint(0, 6) if not mobile else rng.randint(0, 2),
        language_count=rng.randint(1, 4),
        hardware_concurrency=cores,
        device_memory=mem,
        screen_width=sw, screen_height=sh,
        viewport_width=vw, viewport_height=vh,
        touch_points=touch,
        fill_time_ms=rng.uniform(2200, 45000),
        pointer_samples=rng.randint(35, 400) if not mobile else rng.randint(4, 60),
        pointer_entropy=rng.uniform(0.55, 2.4),
        pointer_path_length=path,
        pointer_displacement=displacement,
        keystroke_count=n_keys,
        keystroke_iki_mean=iki_mean,
        # Human typing rhythm is irregular: CV typically 0.25-0.9.
        keystroke_iki_std=iki_mean * rng.uniform(0.25, 0.9),
        paste_used=rng.random() < 0.22,   # password managers paste
        honeypot_filled=False,
    )

    # Real people who look automated. Each of these is a live false-positive
    # source in production bot detection, and omitting them trains a model that
    # locks out exactly the users least able to work around it.
    persona = rng.random()

    if persona < 0.16:
        # Password-manager autofill: credentials appear with no typing at all
        # and the form is submitted almost immediately.
        sig.keystroke_count = 0
        sig.keystroke_iki_mean = 0.0
        sig.keystroke_iki_std = 0.0
        sig.paste_used = True
        sig.fill_time_ms = rng.uniform(400, 2600)

    elif persona < 0.26:
        # Keyboard-only navigation - screen reader or motor-impairment users
        # tab through the form and never move a pointer. Pointer-based features
        # go to their bot-like defaults for an entirely legitimate person.
        sig.pointer_samples = 0
        sig.pointer_entropy = 0.0
        sig.pointer_path_length = 0.0
        sig.pointer_displacement = 0.0
        sig.fill_time_ms = rng.uniform(3000, 30000)

    elif persona < 0.34:
        # Privacy-hardened browser: fingerprinting resistance strips plugins,
        # pins one language and lies about hardware.
        sig.plugin_count = 0
        sig.language_count = 1
        sig.hardware_concurrency = rng.choice([2, 4])
        sig.device_memory = 0.0

    return sig


def _bot_signals(rng: random.Random) -> BotSignals:
    """An automated sign-in attempt, across a range of sophistication."""
    tier = rng.random()

    if tier < 0.42:
        # Naive: obvious headless browser or a bare HTTP client.
        return BotSignals(
            user_agent=rng.choice([
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/122.0.0.0 Safari/537.36",
                "python-requests/2.31.0",
                "curl/8.4.0",
                "Go-http-client/2.0",
                "Scrapy/2.11 (+https://scrapy.org)",
            ]),
            webdriver=rng.random() < 0.85,
            plugin_count=0,
            language_count=rng.randint(0, 1),
            hardware_concurrency=rng.choice([0, 1, 2]),
            device_memory=rng.choice([0, 0, 2]),
            screen_width=rng.choice([0, 800, 1280]),
            screen_height=rng.choice([0, 600, 720]),
            viewport_width=rng.choice([0, 800, 1280]),
            viewport_height=rng.choice([0, 600, 720]),
            touch_points=0,
            fill_time_ms=rng.uniform(20, 700),
            pointer_samples=0,
            pointer_entropy=0.0,
            pointer_path_length=0.0,
            pointer_displacement=0.0,
            keystroke_count=0,
            keystroke_iki_mean=0.0,
            keystroke_iki_std=0.0,
            paste_used=False,
            honeypot_filled=rng.random() < 0.6,
        )

    if tier < 0.78:
        # Mid-tier: a real Chrome under Selenium/Puppeteer with a spoofed UA,
        # synthetic straight-line pointer moves and metronomic typing.
        displacement = rng.uniform(300, 900)
        iki = rng.uniform(30, 110)
        return BotSignals(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            webdriver=rng.random() < 0.5,
            plugin_count=rng.choice([0, 0, 1]),
            language_count=1,
            hardware_concurrency=rng.choice([2, 4]),
            device_memory=rng.choice([0, 4, 8]),
            screen_width=1920, screen_height=1080,
            # Headless renders with no browser chrome: viewport == screen.
            viewport_width=1920, viewport_height=1080,
            touch_points=0,
            fill_time_ms=rng.uniform(300, 2200),
            pointer_samples=rng.randint(2, 14),
            pointer_entropy=rng.uniform(0.0, 0.25),
            pointer_path_length=displacement * rng.uniform(1.0, 1.08),
            pointer_displacement=displacement,
            keystroke_count=rng.randint(8, 26),
            keystroke_iki_mean=iki,
            keystroke_iki_std=iki * rng.uniform(0.0, 0.12),  # near-metronomic
            paste_used=rng.random() < 0.5,
            honeypot_filled=rng.random() < 0.25,
        )

    # Sophisticated: stealth plugin, patched webdriver, jittered typing and
    # curved cursor interpolation. These are meant to be genuinely hard, and
    # some of them *should* be misclassified - that is what keeps the reported
    # metrics honest.
    displacement = rng.uniform(280, 1100)
    iki = rng.uniform(90, 200)
    return BotSignals(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        webdriver=False,
        plugin_count=rng.randint(2, 5),
        language_count=rng.randint(1, 3),
        hardware_concurrency=rng.choice([8, 10, 12]),
        device_memory=rng.choice([8, 16]),
        screen_width=1920, screen_height=1080,
        viewport_width=1680, viewport_height=880,
        touch_points=0,
        fill_time_ms=rng.uniform(1800, 9000),
        pointer_samples=rng.randint(25, 120),
        pointer_entropy=rng.uniform(0.3, 1.1),
        pointer_path_length=displacement * rng.uniform(1.15, 1.9),
        pointer_displacement=displacement,
        keystroke_count=rng.randint(12, 30),
        keystroke_iki_mean=iki,
        keystroke_iki_std=iki * rng.uniform(0.15, 0.55),
        paste_used=rng.random() < 0.3,
        honeypot_filled=False,
    )


def generate_bot_dataset(n: int = 9000, seed: int = 20260814,
                         bot_fraction: float = 0.42,
                         label_noise: float = 0.02
                         ) -> Tuple[List[List[float]], List[int]]:
    """Simulate human and automated sign-ins and return ``(X, y)``.

    ``label_noise`` flips a small share of labels. Bot ground truth is normally
    assembled from downstream outcomes - chargebacks, abuse reports, manual
    review - all of which are imperfect, so a model that fits its labels
    perfectly is a model that has fitted the labelling process rather than the
    behaviour.
    """
    rng = random.Random(seed)
    X: List[List[float]] = []
    y: List[int] = []
    for _ in range(n):
        if rng.random() < bot_fraction:
            X.append(bot_vector(_bot_signals(rng)))
            label = 1
        else:
            X.append(bot_vector(_human_signals(rng)))
            label = 0
        if rng.random() < label_noise:
            label = 1 - label
        y.append(label)
    return X, y
