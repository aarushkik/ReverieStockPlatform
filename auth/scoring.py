"""
Serving layer: loads the trained models and turns a sign-in into a decision.

Two principles shape this module.

**A model score is not a decision.** The classifier returns a calibrated
probability; what to *do* about it is policy, and policy here is graded -
``ALLOW`` / ``CHALLENGE`` / ``DENY`` - rather than a binary pass-fail. A trading
account should ask for a second factor when something looks off, not slam the
door, because the cost of locking out the real user is high and the cost of one
extra challenge is low.

**Deterministic rules outrank the model in both directions.** A journey that
would need Mach 5 is not "probably suspicious", it is impossible, and no model
output should be able to wave it through; equally, a filled honeypot field is
not evidence, it is proof. Hard rules can raise a decision, and a small set of
trust rules can lower it. The model handles the wide grey band in between,
which is the part rules are bad at.

Every assessment carries human-readable reasons. An unexplained risk score is
unactionable for the user staring at a challenge prompt and unauditable for
whoever reviews the log later.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from . import geo
from .features import (
    BOT_FEATURES,
    LOGIN_FEATURES,
    BotSignals,
    LoginAttempt,
    bot_vector,
    extract_bot_features,
    extract_login_features,
    login_vector,
)

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
LOGIN_MODEL_PATH = os.path.join(MODEL_DIR, "login_risk.joblib")
BOT_MODEL_PATH = os.path.join(MODEL_DIR, "bot_detector.joblib")

# Decisions, in increasing order of severity.
ALLOW = "allow"
CHALLENGE = "challenge"
DENY = "deny"
_SEVERITY = {ALLOW: 0, CHALLENGE: 1, DENY: 2}

# Risk bands for presentation. Thresholds come from the calibrated model, so
# they are probabilities and mean what they say.
BAND_LOW = "low"
BAND_ELEVATED = "elevated"
BAND_HIGH = "high"

CHALLENGE_THRESHOLD = 0.35
DENY_THRESHOLD = 0.85
BOT_THRESHOLD = 0.80

_lock = threading.Lock()
_cache: Dict[str, object] = {}


class ModelUnavailable(RuntimeError):
    """Raised when a model artifact is missing or its schema does not match."""


def _load(path: str, expected_features: List[str], key: str):
    """Load a persisted model, asserting its feature order still matches.

    Feature order is the silent killer for a deployed model: reorder a list in
    features.py, redeploy without retraining, and every score is quietly
    computed from mismatched columns. Nothing raises; the numbers just become
    meaningless. Checking the pinned order from the artifact against the live
    schema turns that into a startup failure.
    """
    with _lock:
        if key in _cache:
            return _cache[key]
        if not os.path.exists(path):
            raise ModelUnavailable(
                f"{os.path.basename(path)} not found. Run: python -m auth.train"
            )
        import joblib

        bundle = joblib.load(path)
        stored = list(bundle.get("features", []))
        if stored != expected_features:
            raise ModelUnavailable(
                f"{os.path.basename(path)} was trained on a different feature "
                f"schema ({len(stored)} features) than features.py defines "
                f"({len(expected_features)}). Retrain: python -m auth.train"
            )
        _cache[key] = bundle["model"]
        return _cache[key]


def models_available() -> bool:
    return os.path.exists(LOGIN_MODEL_PATH) and os.path.exists(BOT_MODEL_PATH)


# ==============================================================================
# ASSESSMENTS
# ==============================================================================


@dataclass
class RiskAssessment:
    """The outcome of scoring one sign-in attempt."""

    score: float = 0.0                       # calibrated P(suspicious)
    decision: str = ALLOW
    band: str = BAND_LOW
    reasons: List[str] = field(default_factory=list)
    hard_rules: List[str] = field(default_factory=list)
    features: Dict[str, float] = field(default_factory=dict)
    location: Optional[geo.GeoLocation] = None
    model_available: bool = True

    @property
    def requires_challenge(self) -> bool:
        return self.decision in (CHALLENGE, DENY)

    @property
    def percent(self) -> int:
        return int(round(self.score * 100))


@dataclass
class BotAssessment:
    """The outcome of scoring the client telemetry behind a sign-in."""

    score: float = 0.0                       # calibrated P(automated)
    is_bot: bool = False
    reasons: List[str] = field(default_factory=list)
    hard_rules: List[str] = field(default_factory=list)
    features: Dict[str, float] = field(default_factory=dict)
    model_available: bool = True


def _band(score: float) -> str:
    if score >= DENY_THRESHOLD:
        return BAND_HIGH
    if score >= CHALLENGE_THRESHOLD:
        return BAND_ELEVATED
    return BAND_LOW


def _escalate(current: str, proposed: str) -> str:
    """Return whichever decision is more severe."""
    return proposed if _SEVERITY[proposed] > _SEVERITY[current] else current


# ==============================================================================
# LOGIN RISK
# ==============================================================================


def _login_reasons(f: Dict[str, float], loc: geo.GeoLocation) -> List[str]:
    """Plain-language explanations for whatever drove the score up."""
    import math

    reasons: List[str] = []

    velocity = math.expm1(f["log_velocity_kmh"])
    distance = math.expm1(f["log_distance_km"])
    hours = math.expm1(f["log_hours_since_last"])

    if f["impossible_travel"]:
        reasons.append(
            f"Implied travel of {distance:,.0f} km in {hours:.1f} h "
            f"({velocity:,.0f} km/h) is faster than any commercial flight"
        )
    elif velocity > 400:
        reasons.append(f"Rapid location change: {distance:,.0f} km in {hours:.1f} h")

    if f["new_country"]:
        reasons.append(f"First sign-in from {loc.country or loc.country_code or 'this country'}")
    elif f["new_city"]:
        reasons.append(f"First sign-in from {loc.city or 'this city'}")

    if f["new_device"]:
        reasons.append("Unrecognised device")
    if f["is_hosting_asn"]:
        reasons.append(f"Connection from a datacenter network{' (' + loc.org + ')' if loc.org else ''}")
    if f["is_proxy"]:
        reasons.append("Connection through a known VPN, proxy or Tor exit")
    if f["geo_unresolved"]:
        reasons.append("Network location could not be resolved")
    if f["tz_mismatch"]:
        reasons.append("Browser timezone disagrees with the network location")
    if f["failed_attempts_1h"] >= 4:
        reasons.append(f"{int(f['failed_attempts_1h'])} failed attempts in the past hour")
    if f["hour_deviation"] > 0.55:
        reasons.append("Sign-in well outside this account's usual hours")
    if f["log_account_age_days"] < 2.0:
        reasons.append("Account created recently")

    return reasons


def score_login(attempt: LoginAttempt) -> RiskAssessment:
    """Score a sign-in attempt and decide what to do about it."""
    feats = extract_login_features(attempt)
    loc = attempt.location

    assessment = RiskAssessment(features=feats, location=loc)

    try:
        model = _load(LOGIN_MODEL_PATH, LOGIN_FEATURES, "login")
        vector = [feats[name] for name in LOGIN_FEATURES]
        assessment.score = float(model.predict_proba([vector])[0][1])
    except ModelUnavailable:
        # Degrade to rules alone rather than failing open. An unavailable model
        # must not turn into an unconditional allow.
        assessment.model_available = False
        assessment.score = 0.5 if feats["impossible_travel"] else 0.15

    assessment.reasons = _login_reasons(feats, loc)

    # ---- policy ---------------------------------------------------------
    if assessment.score >= DENY_THRESHOLD:
        assessment.decision = DENY
    elif assessment.score >= CHALLENGE_THRESHOLD:
        assessment.decision = CHALLENGE

    # ---- hard rules that can only escalate ------------------------------
    # Physical impossibility is not a probability. Whatever the model thinks,
    # one of the two locations is wrong or one of the sessions is not the user.
    if feats["impossible_travel"]:
        assessment.decision = _escalate(assessment.decision, CHALLENGE)
        assessment.hard_rules.append("impossible_travel")

    # Datacenter origin plus an unrecognised device is the credential-stuffing
    # signature; neither alone is worth a challenge, together they are.
    if feats["is_hosting_asn"] and feats["new_device"]:
        assessment.decision = _escalate(assessment.decision, CHALLENGE)
        assessment.hard_rules.append("datacenter_origin_new_device")

    if feats["failed_attempts_1h"] >= 8:
        assessment.decision = _escalate(assessment.decision, CHALLENGE)
        assessment.hard_rules.append("failed_attempt_burst")

    # ---- trust rules that can de-escalate -------------------------------
    # A known device on a known network in a known country, with no failures,
    # is the overwhelmingly common case. Challenging it trains users to click
    # through prompts without reading them, which costs more security than it
    # buys. Never de-escalates past a hard rule.
    if (
        not assessment.hard_rules
        and feats["device_familiarity"] > 0.5
        and feats["asn_familiarity"] > 0.3
        and not feats["new_country"]
        and feats["failed_attempts_1h"] < 3
        and assessment.decision == CHALLENGE
        and assessment.score < 0.6
    ):
        assessment.decision = ALLOW
        assessment.reasons.append("Recognised device on a familiar network")

    assessment.band = _band(assessment.score)
    if assessment.decision == DENY:
        assessment.band = BAND_HIGH
    elif assessment.decision == CHALLENGE and assessment.band == BAND_LOW:
        assessment.band = BAND_ELEVATED

    return assessment


# ==============================================================================
# BOT DETECTION
# ==============================================================================


def _bot_reasons(f: Dict[str, float], sig: BotSignals) -> List[str]:
    reasons: List[str] = []
    if f["honeypot_filled"]:
        reasons.append("Hidden form field was filled in")
    if f["webdriver_flag"]:
        reasons.append("Browser reports it is under automation control")
    if f["headless_ua"]:
        reasons.append("Client identifies as a headless browser or HTTP library")
    if f["no_interaction"]:
        reasons.append("Form submitted with no pointer movement and no typing")
    if f["pointer_samples"] > 0 and f["pointer_straightness"] > 0.95:
        reasons.append("Pointer moved in a perfectly straight line")
    if f["keystroke_count"] >= 3 and f["keystroke_iki_cv"] < 0.08:
        reasons.append("Typing rhythm is unnaturally regular")
    if sig.fill_time_ms and sig.fill_time_ms < 400 and f["keystroke_count"] > 0:
        reasons.append(f"Form completed in {sig.fill_time_ms:.0f} ms")
    if f["screen_plausible"] < 0.5:
        reasons.append("Reported screen and viewport dimensions are inconsistent")
    if f["touch_ua_agreement"] < 0.5:
        reasons.append("Touch capability disagrees with the reported platform")
    return reasons


def score_bot(sig: BotSignals) -> BotAssessment:
    """Score client telemetry for automation."""
    feats = extract_bot_features(sig)
    assessment = BotAssessment(features=feats)

    try:
        model = _load(BOT_MODEL_PATH, BOT_FEATURES, "bot")
        vector = [feats[name] for name in BOT_FEATURES]
        assessment.score = float(model.predict_proba([vector])[0][1])
    except ModelUnavailable:
        assessment.model_available = False
        assessment.score = 0.9 if (feats["honeypot_filled"] or feats["webdriver_flag"]) else 0.1

    assessment.reasons = _bot_reasons(feats, sig)
    assessment.is_bot = assessment.score >= BOT_THRESHOLD

    # A honeypot is a hidden field with no label and no tab stop. No human
    # fills it; only something parsing the DOM does. This is proof, not
    # evidence, so it overrides the model outright.
    if feats["honeypot_filled"]:
        assessment.is_bot = True
        assessment.hard_rules.append("honeypot")

    # navigator.webdriver is trivially patched, so its absence proves nothing -
    # but a client that leaves it set is telling the truth about itself.
    if feats["webdriver_flag"]:
        assessment.is_bot = True
        assessment.hard_rules.append("webdriver")

    if feats["headless_ua"]:
        assessment.is_bot = True
        assessment.hard_rules.append("headless_user_agent")

    return assessment


def model_cards() -> Dict[str, dict]:
    """Load both model cards for display in the security console."""
    import json

    cards = {}
    for name, path in (
        ("login_risk", os.path.join(MODEL_DIR, "login_risk.card.json")),
        ("bot_detector", os.path.join(MODEL_DIR, "bot_detector.card.json")),
    ):
        try:
            with open(path) as fh:
                cards[name] = json.load(fh)
        except (OSError, ValueError):
            cards[name] = {}
    return cards
