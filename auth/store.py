"""
User records, credential verification and the sign-in event log.

Storage is a JSON file guarded by a process lock. That is appropriate for a
single-process Streamlit deployment and explicitly is not a production
identity store: there is no replication, no cross-process locking beyond an
atomic replace, and no key rotation. The interface is narrow enough that
swapping in a real database means reimplementing this module and nothing else.

What *is* production-shaped is the credential handling, because getting that
wrong is unrecoverable:

* Passwords are stored as scrypt hashes with a 16-byte random per-user salt.
  scrypt is memory-hard, so unlike PBKDF2 or bcrypt it resists GPU and ASIC
  cracking rigs, which is the realistic threat against a leaked hash file.

* Verification is constant-time via ``hmac.compare_digest``.

* Verifying an unknown username still performs a full scrypt computation
  against a dummy hash. Returning early would make failures for existing
  accounts measurably slower than for non-existent ones, letting an attacker
  enumerate valid usernames with a stopwatch.

* The event log records the metadata the risk model needs and nothing more. It
  stores the resolved city and coarse coordinates, not the raw IP, and never
  stores anything derived from the password.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .features import LoginEvent

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
USERS_PATH = os.path.join(DATA_DIR, "users.json")
EVENTS_PATH = os.path.join(DATA_DIR, "login_events.json")

# scrypt parameters. n=2**15 with r=8 costs 128*N*r = 32 MiB and ~100 ms per
# verification on commodity hardware - slow enough to make offline cracking
# expensive, fast enough not to be a login-time DoS vector.
_SCRYPT_N = 2 ** 15
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
# OpenSSL defaults maxmem to exactly 32 MiB, which these parameters sit right
# on top of, so the call fails without an explicit ceiling. 96 MiB leaves room
# for the allocation plus overhead without inviting memory exhaustion.
_SCRYPT_MAXMEM = 96 * 1024 * 1024

# How many past sign-ins the risk model is given as history. Enough to
# establish habitual location, network and hours without unbounded growth.
HISTORY_WINDOW = 60

# Retention for the raw event log.
EVENT_RETENTION_DAYS = 180

_lock = threading.RLock()

# A fixed decoy hash so unknown-user verification does the same work as a real
# one. Generated once at import from a random password nobody holds.
_DUMMY_SALT = b"\x00" * 16
_DUMMY_HASH = hashlib.scrypt(
    secrets.token_bytes(32), salt=_DUMMY_SALT,
    n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN,
    maxmem=_SCRYPT_MAXMEM,
)


# ==============================================================================
# RECORDS
# ==============================================================================


@dataclass
class User:
    username: str
    password_hash: str = ""     # hex
    password_salt: str = ""     # hex
    display_name: str = ""
    created_at: float = 0.0
    last_login: float = 0.0
    known_devices: List[str] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)

    @property
    def account_age_days(self) -> float:
        if not self.created_at:
            return 0.0
        return max(0.0, (time.time() - self.created_at) / 86400.0)


# ==============================================================================
# PERSISTENCE
# ==============================================================================


def _ensure_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _read_json(path: str, default):
    try:
        with open(path, "r") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _write_json(path: str, payload) -> None:
    """Write atomically so a crash mid-write cannot truncate the store."""
    _ensure_dir()
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w") as fh:
        json.dump(payload, fh, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _load_users() -> Dict[str, User]:
    raw = _read_json(USERS_PATH, {})
    users: Dict[str, User] = {}
    for name, data in (raw or {}).items():
        known = {k: v for k, v in data.items() if k in User.__annotations__}
        users[name] = User(**known)
    return users


def _save_users(users: Dict[str, User]) -> None:
    _write_json(USERS_PATH, {name: asdict(u) for name, u in users.items()})


# ==============================================================================
# CREDENTIALS
# ==============================================================================


def hash_password(password: str, salt: Optional[bytes] = None) -> tuple:
    """Return ``(hash_hex, salt_hex)`` for *password*."""
    if salt is None:
        salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt,
        n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN,
        maxmem=_SCRYPT_MAXMEM,
    )
    return digest.hex(), salt.hex()


def verify_password(password: str, hash_hex: str, salt_hex: str) -> bool:
    """Constant-time credential check."""
    try:
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except ValueError:
        return False
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt,
        n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN,
        maxmem=_SCRYPT_MAXMEM,
    )
    return hmac.compare_digest(digest, expected)


def authenticate(username: str, password: str) -> Optional[User]:
    """Verify credentials, returning the user or ``None``.

    Unknown usernames still run a full scrypt computation against a decoy hash.
    Returning early would leave a timing gap wide enough to enumerate valid
    accounts, since scrypt at these parameters takes ~100 ms and the difference
    would be trivially measurable over the network.
    """
    with _lock:
        users = _load_users()
        user = users.get((username or "").strip().lower())

    if user is None:
        hmac.compare_digest(
            hashlib.scrypt(
                (password or "").encode("utf-8"), salt=_DUMMY_SALT,
                n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN,
                maxmem=_SCRYPT_MAXMEM,
            ),
            _DUMMY_HASH,
        )
        return None

    if verify_password(password or "", user.password_hash, user.password_salt):
        return user
    return None


# ==============================================================================
# USER MANAGEMENT
# ==============================================================================


def get_user(username: str) -> Optional[User]:
    with _lock:
        return _load_users().get((username or "").strip().lower())


def list_users() -> List[User]:
    with _lock:
        return list(_load_users().values())


def create_user(username: str, password: str, display_name: str = "") -> User:
    """Create an account. Raises ``ValueError`` if the username is taken."""
    username = (username or "").strip().lower()
    if not username:
        raise ValueError("Username is required")
    if len(password or "") < 8:
        raise ValueError("Password must be at least 8 characters")

    with _lock:
        users = _load_users()
        if username in users:
            raise ValueError("That username is already taken")
        pw_hash, pw_salt = hash_password(password)
        user = User(
            username=username,
            password_hash=pw_hash,
            password_salt=pw_salt,
            display_name=display_name or username,
            created_at=time.time(),
        )
        users[username] = user
        _save_users(users)
    return user


def update_user(username: str, **changes) -> Optional[User]:
    """Patch mutable fields on a user record."""
    username = (username or "").strip().lower()
    with _lock:
        users = _load_users()
        user = users.get(username)
        if user is None:
            return None
        for key, value in changes.items():
            # password_hash/salt are only ever set through set_password().
            if key in ("display_name", "last_login", "known_devices", "preferences"):
                setattr(user, key, value)
        _save_users(users)
        return user


def set_password(username: str, new_password: str) -> bool:
    if len(new_password or "") < 8:
        raise ValueError("Password must be at least 8 characters")
    username = (username or "").strip().lower()
    with _lock:
        users = _load_users()
        user = users.get(username)
        if user is None:
            return False
        user.password_hash, user.password_salt = hash_password(new_password)
        _save_users(users)
        return True


def remember_device(username: str, device_id: str) -> None:
    """Add a device fingerprint to the user's known set."""
    if not device_id:
        return
    username = (username or "").strip().lower()
    with _lock:
        users = _load_users()
        user = users.get(username)
        if user is None:
            return
        if device_id not in user.known_devices:
            user.known_devices.append(device_id)
            user.known_devices = user.known_devices[-25:]
            _save_users(users)


# ==============================================================================
# EVENT LOG
# ==============================================================================


def _load_events() -> List[Dict[str, Any]]:
    return _read_json(EVENTS_PATH, []) or []


def record_event(
    username: str,
    *,
    success: bool,
    decision: str,
    risk_score: float,
    bot_score: float,
    location: Any,
    device_id: str,
    reasons: Optional[List[str]] = None,
    hard_rules: Optional[List[str]] = None,
) -> None:
    """Append a sign-in attempt to the audit log.

    Deliberately stores the resolved place and coarse coordinates rather than
    the raw IP: the risk model needs geography, not the address, and an
    unnecessary IP log is a liability in a breach. Coordinates are rounded to
    ~1 km, which is finer than IP geolocation is accurate anyway.
    """
    entry = {
        "timestamp": time.time(),
        "username": (username or "").strip().lower(),
        "success": bool(success),
        "decision": decision,
        "risk_score": round(float(risk_score), 4),
        "bot_score": round(float(bot_score), 4),
        "device_id": device_id or "",
        "city": getattr(location, "city", "") or "",
        "country_code": getattr(location, "country_code", "") or "",
        "asn": getattr(location, "asn", "") or "",
        "org": getattr(location, "org", "") or "",
        "latitude": round(getattr(location, "latitude", None) or 0.0, 2) or None,
        "longitude": round(getattr(location, "longitude", None) or 0.0, 2) or None,
        "is_hosting": bool(getattr(location, "is_hosting", False)),
        "is_proxy": bool(getattr(location, "is_proxy", False)),
        "reasons": list(reasons or []),
        "hard_rules": list(hard_rules or []),
    }

    with _lock:
        events = _load_events()
        events.append(entry)
        cutoff = time.time() - EVENT_RETENTION_DAYS * 86400
        events = [e for e in events if e.get("timestamp", 0) >= cutoff][-5000:]
        _write_json(EVENTS_PATH, events)


def get_events(username: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Most recent events first, optionally filtered to one account."""
    with _lock:
        events = _load_events()
    if username:
        target = username.strip().lower()
        events = [e for e in events if e.get("username") == target]
    return sorted(events, key=lambda e: e.get("timestamp", 0), reverse=True)[:limit]


def get_login_history(username: str, limit: int = HISTORY_WINDOW) -> List[LoginEvent]:
    """Successful sign-ins as model input, oldest first.

    Only successful logins count as history. Including failures would let an
    attacker seed their own location into the baseline just by failing at it
    repeatedly, which would erase the travel signal they are trying to evade.
    """
    with _lock:
        events = _load_events()
    target = (username or "").strip().lower()
    rows = [
        e for e in events
        if e.get("username") == target and e.get("success") and e.get("decision") != "deny"
    ]
    rows.sort(key=lambda e: e.get("timestamp", 0))
    return [
        LoginEvent(
            timestamp=e.get("timestamp", 0.0),
            latitude=e.get("latitude"),
            longitude=e.get("longitude"),
            city=e.get("city", ""),
            country_code=e.get("country_code", ""),
            asn=e.get("asn", ""),
            device_id=e.get("device_id", ""),
        )
        for e in rows[-limit:]
    ]


def count_recent_failures(username: str, within_seconds: float = 3600) -> int:
    """Failed attempts against an account inside the window."""
    cutoff = time.time() - within_seconds
    target = (username or "").strip().lower()
    with _lock:
        events = _load_events()
    return sum(
        1 for e in events
        if e.get("username") == target
        and not e.get("success")
        and e.get("timestamp", 0) >= cutoff
    )


def count_recent_attempts(username: str, within_seconds: float = 86400) -> int:
    """All attempts against an account inside the window."""
    cutoff = time.time() - within_seconds
    target = (username or "").strip().lower()
    with _lock:
        events = _load_events()
    return sum(
        1 for e in events
        if e.get("username") == target and e.get("timestamp", 0) >= cutoff
    )


def export_training_rows() -> List[Dict[str, Any]]:
    """Every logged event, for retraining the risk model on real data.

    The schema here matches what ``datasets.generate_login_dataset`` simulates,
    so moving from synthetic to real training data is a change of source rather
    than a rewrite of the pipeline.
    """
    with _lock:
        return list(_load_events())
