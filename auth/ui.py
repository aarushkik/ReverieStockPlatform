"""
The sign-in screen and the session gate.

The credential form is a Streamlit component rather than a stack of
``st.text_input`` widgets, for one reason: the bot detector needs to observe
how the form was filled - pointer path, keystroke rhythm, time from first
interaction to submit - and Streamlit's own widgets rerun the script on every
keystroke, which both destroys the timing signal and makes typing feel laggy.
Owning the form means one round trip on submit, full telemetry fidelity, and a
login screen that can actually be designed.

The password travels over the same Streamlit websocket a ``st.text_input``
would use. It is passed straight to ``store.authenticate`` and is never logged,
never written to session state, and never included in an event record.
"""

from __future__ import annotations

import os
import secrets
import time
from typing import Optional

import streamlit as st

import theme as theme_mod
import ui_effects as fx

from . import geo, scoring, store
from .features import BotSignals, LoginAttempt
from .telemetry import DEVICE_ID_JS, TELEMETRY_JS

SESSION_USER = "auth_user"
SESSION_STARTED = "auth_session_started"
SESSION_RISK = "auth_last_risk"
SESSION_PENDING = "auth_pending_challenge"

# Sessions expire after this long, after which credentials are required again.
SESSION_MAX_AGE_S = 12 * 3600

# Salts the device identifier so it cannot be correlated across deployments.
_DEVICE_SALT = os.environ.get("DEVICE_ID_SALT", "reverie-terminal-v1")


# ==============================================================================
# COMPONENT
# ==============================================================================

_LOGIN_HTML = """
<div class="rv-auth-shell">
  <form class="rv-auth-card" id="rv-auth-form" autocomplete="on">
    <div class="rv-auth-head">
      <div class="rv-auth-mark">R</div>
      <div>
        <div class="rv-auth-title">Reverie Terminal</div>
        <div class="rv-auth-sub" id="rv-auth-sub">Secure sign-in</div>
      </div>
    </div>

    <div class="rv-auth-modes" role="tablist">
      <button type="button" class="rv-auth-mode is-active" id="rv-mode-signin"
              role="tab" aria-selected="true">Sign in</button>
      <button type="button" class="rv-auth-mode" id="rv-mode-signup"
              role="tab" aria-selected="false">Create account</button>
    </div>

    <label class="rv-auth-label" for="rv-user">Username</label>
    <input class="rv-auth-input" id="rv-user" name="username"
           type="text" autocomplete="username" spellcheck="false"
           autocapitalize="none" placeholder="trader" />

    <label class="rv-auth-label" for="rv-pass">Password</label>
    <div class="rv-auth-passwrap">
      <input class="rv-auth-input" id="rv-pass" name="password"
             type="password" autocomplete="current-password"
             placeholder="Enter your password" />
      <button type="button" class="rv-auth-peek" id="rv-peek"
              aria-label="Show password" title="Show password">show</button>
    </div>

    <div id="rv-signup-only" hidden>
      <label class="rv-auth-label" for="rv-pass2">Confirm password</label>
      <input class="rv-auth-input" id="rv-pass2" name="confirm"
             type="password" autocomplete="new-password"
             placeholder="Re-enter your password" />

      <label class="rv-auth-label" for="rv-display">Display name
        <span class="rv-auth-optional">optional</span></label>
      <input class="rv-auth-input" id="rv-display" name="display"
             type="text" autocomplete="name" placeholder="Ada Lovelace" />
    </div>

    <!-- Honeypot. Off-screen, aria-hidden and removed from the tab order, so
         no person and no assistive technology can reach it. Anything that
         fills it is reading the DOM rather than using the page. -->
    <div class="rv-auth-hp" aria-hidden="true">
      <label for="rv-company">Company</label>
      <input id="rv-company" name="company" type="text"
             tabindex="-1" autocomplete="off" />
    </div>

    <div class="rv-auth-error" id="rv-auth-error" role="alert"></div>

    <button class="rv-auth-submit" id="rv-auth-submit" type="submit">
      <span id="rv-auth-submit-label">Sign in</span>
    </button>

    <div class="rv-auth-foot">
      <span class="rv-auth-shield">&#9679;</span>
      <span id="rv-auth-foot-text">Protected by device, location and behaviour analysis</span>
    </div>
  </form>
</div>
"""

_LOGIN_CSS = """
.rv-auth-shell {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 78vh;
  padding: 24px 16px;
  font-family: var(--rv-font, 'Inter', sans-serif);
  position: relative;
  z-index: 5;
}
.rv-auth-card {
  width: 100%;
  max-width: 400px;
  background: var(--rv-surface, #111621);
  border: 1px solid var(--rv-border, #212A3B);
  border-radius: var(--rv-radius-lg, 14px);
  padding: 28px;
  box-shadow: var(--rv-shadow-3, 0 12px 40px rgba(0,0,0,.45));
  display: flex;
  flex-direction: column;
  animation: rv-auth-in .5s cubic-bezier(.16,1,.3,1) both;
}
@keyframes rv-auth-in {
  from { opacity: 0; transform: translateY(14px) scale(.985); }
  to   { opacity: 1; transform: none; }
}
.rv-auth-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}
.rv-auth-mark {
  width: 38px; height: 38px;
  flex: none;
  border-radius: 10px;
  background: var(--rv-accent-fill, #00D68F);
  color: var(--rv-on-accent, #04140E);
  display: flex; align-items: center; justify-content: center;
  font-weight: 800; font-size: 19px;
  letter-spacing: -0.02em;
}
.rv-auth-title {
  font-size: 16px; font-weight: 650;
  color: var(--rv-text, #E8EDF5);
  letter-spacing: -0.01em;
  line-height: 1.2;
}
.rv-auth-sub {
  font-size: 12px;
  color: var(--rv-text-muted, #93A1B8);
  margin-top: 2px;
}
.rv-auth-modes {
  display: flex;
  gap: 3px;
  background: var(--rv-surface-alt, #161C29);
  border: 1px solid var(--rv-border, #212A3B);
  border-radius: var(--rv-radius-sm, 6px);
  padding: 3px;
  margin-bottom: 20px;
}
.rv-auth-mode {
  flex: 1;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: var(--rv-text-muted, #93A1B8);
  font-family: inherit;
  font-size: 12.5px;
  font-weight: 600;
  padding: 7px 6px;
  cursor: pointer;
  transition: background .18s ease, color .18s ease;
}
.rv-auth-mode:hover { color: var(--rv-text, #E8EDF5); }
.rv-auth-mode.is-active {
  background: var(--rv-surface-hi, #1C2333);
  color: var(--rv-text, #E8EDF5);
  box-shadow: 0 1px 2px rgba(0,0,0,.28);
}
.rv-auth-optional {
  text-transform: none;
  letter-spacing: 0;
  font-weight: 500;
  color: var(--rv-text-faint, #7A88A0);
  opacity: .8;
  margin-left: 5px;
}
.rv-auth-hint {
  font-size: 11.5px;
  color: var(--rv-text-faint, #7A88A0);
  margin: -8px 0 14px;
  line-height: 1.45;
}
.rv-auth-label {
  font-size: 11px; font-weight: 600;
  text-transform: uppercase; letter-spacing: .07em;
  color: var(--rv-text-faint, #7A88A0);
  margin-bottom: 6px;
}
.rv-auth-input {
  width: 100%;
  box-sizing: border-box;
  background: var(--rv-surface-alt, #161C29);
  border: 1px solid var(--rv-border, #212A3B);
  border-radius: var(--rv-radius-sm, 6px);
  color: var(--rv-text, #E8EDF5);
  font-family: inherit;
  font-size: 14px;
  padding: 11px 12px;
  margin-bottom: 16px;
  outline: none;
  transition: border-color .18s ease, box-shadow .18s ease;
}
.rv-auth-input::placeholder { color: var(--rv-text-faint, #7A88A0); opacity: .7; }
.rv-auth-input:focus {
  border-color: var(--rv-accent-fill, #00D68F);
  box-shadow: 0 0 0 3px var(--rv-accent-soft, rgba(0,214,143,.14));
}
.rv-auth-passwrap { position: relative; }
.rv-auth-peek {
  position: absolute;
  right: 8px; top: 9px;
  background: transparent;
  border: none;
  color: var(--rv-text-faint, #7A88A0);
  font-family: inherit;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .06em;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 4px;
}
.rv-auth-peek:hover { color: var(--rv-text, #E8EDF5); background: var(--rv-surface-hi, #1C2333); }

/* Off-screen rather than display:none - some scrapers skip hidden fields but
   fill anything present in the DOM. */
.rv-auth-hp {
  position: absolute !important;
  left: -9999px !important;
  width: 1px; height: 1px;
  overflow: hidden;
}

.rv-auth-error {
  display: none;
  font-size: 12.5px;
  line-height: 1.45;
  color: var(--rv-neg, #FF4D6A);
  background: var(--rv-neg-soft, rgba(255,77,106,.14));
  border: 1px solid var(--rv-neg, #FF4D6A);
  border-radius: var(--rv-radius-sm, 6px);
  padding: 9px 11px;
  margin-bottom: 14px;
}
.rv-auth-error.show { display: block; animation: rv-shake .32s ease; }
@keyframes rv-shake {
  0%,100% { transform: translateX(0); }
  25% { transform: translateX(-5px); }
  75% { transform: translateX(5px); }
}

.rv-auth-submit {
  width: 100%;
  background: var(--rv-accent-fill, #00D68F);
  color: var(--rv-on-accent, #04140E);
  border: none;
  border-radius: var(--rv-radius-sm, 6px);
  font-family: inherit;
  font-size: 13.5px;
  font-weight: 700;
  padding: 12px;
  cursor: pointer;
  transition: filter .18s ease, transform .12s ease;
}
.rv-auth-submit:hover:not(:disabled) { filter: brightness(1.08); }
.rv-auth-submit:active:not(:disabled) { transform: translateY(1px); }
.rv-auth-submit:disabled { opacity: .6; cursor: progress; }

.rv-auth-foot {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 18px;
  font-size: 11px;
  color: var(--rv-text-faint, #7A88A0);
  line-height: 1.4;
}
.rv-auth-shield { color: var(--rv-accent-fill, #00D68F); font-size: 8px; }

@media (prefers-reduced-motion: reduce) {
  .rv-auth-card { animation: none; }
  .rv-auth-error.show { animation: none; }
}
"""

_LOGIN_JS = (
    TELEMETRY_JS
    + DEVICE_ID_JS
    + r"""
export default function (component) {
  const { data, parentElement, setTriggerValue } = component;
  const q = (sel) => parentElement.querySelector(sel);

  const form = q('#rv-auth-form');
  const userEl = q('#rv-user');
  const passEl = q('#rv-pass');
  const pass2El = q('#rv-pass2');
  const displayEl = q('#rv-display');
  const signupBox = q('#rv-signup-only');
  const modeSignIn = q('#rv-mode-signin');
  const modeSignUp = q('#rv-mode-signup');
  const hpEl = q('#rv-company');
  const errEl = q('#rv-auth-error');
  const submitEl = q('#rv-auth-submit');
  const labelEl = q('#rv-auth-submit-label');
  const peekEl = q('#rv-peek');
  const subEl = q('#rv-auth-sub');
  const footEl = q('#rv-auth-foot-text');
  if (!form) return;

  let mode = (data.mode === 'signup') ? 'signup' : 'signin';

  function applyMode(next) {
    mode = next;
    const up = mode === 'signup';
    signupBox.hidden = !up;
    modeSignUp.classList.toggle('is-active', up);
    modeSignIn.classList.toggle('is-active', !up);
    modeSignUp.setAttribute('aria-selected', String(up));
    modeSignIn.setAttribute('aria-selected', String(!up));
    labelEl.textContent = up ? 'Create account' : 'Sign in';
    subEl.textContent = up ? 'Create your account' : 'Secure sign-in';
    footEl.textContent = up
      ? 'New accounts are checked for automation before they are created'
      : 'Protected by device, location and behaviour analysis';
    // A password manager should offer to save on signup and to fill on
    // sign-in; the autocomplete token is what tells it which.
    passEl.setAttribute('autocomplete', up ? 'new-password' : 'current-password');
    errEl.classList.remove('show');
    submitEl.disabled = false;
  }

  modeSignIn.onclick = () => applyMode('signin');
  modeSignUp.onclick = () => applyMode('signup');
  applyMode(mode);

  // Telemetry listens on the whole document: the pointer travels across the
  // page before it reaches the form, and that approach path is exactly the
  // signal we want.
  const probe = createTelemetry(document);
  const deviceId = deriveDeviceId(data.device_salt || 'reverie');

  if (data.error) {
    errEl.textContent = data.error;
    errEl.classList.add('show');
  }
  if (data.subtitle) subEl.textContent = data.subtitle;

  peekEl.onclick = () => {
    const showing = passEl.type === 'text';
    passEl.type = showing ? 'password' : 'text';
    peekEl.textContent = showing ? 'show' : 'hide';
    peekEl.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');
    passEl.focus();
  };

  function fail(message) {
    errEl.textContent = message;
    errEl.classList.add('show');
    submitEl.disabled = false;
    labelEl.textContent = mode === 'signup' ? 'Create account' : 'Sign in';
  }

  form.onsubmit = (e) => {
    e.preventDefault();
    const username = (userEl.value || '').trim();
    const password = passEl.value || '';

    if (!username || !password) {
      fail('Enter both a username and a password.');
      return;
    }

    // Client-side checks are a courtesy so the user is not made to wait on a
    // round trip for an obvious mistake. The server re-validates all of it.
    if (mode === 'signup') {
      if (password.length < 8) {
        fail('Password must be at least 8 characters.');
        return;
      }
      if (password !== (pass2El.value || '')) {
        fail('The two passwords do not match.');
        return;
      }
    }

    submitEl.disabled = true;
    labelEl.textContent = mode === 'signup' ? 'Creating…' : 'Verifying…';
    errEl.classList.remove('show');

    setTriggerValue('submit', {
      mode: mode,
      username: username,
      password: password,
      confirm: pass2El ? (pass2El.value || '') : '',
      display_name: displayEl ? (displayEl.value || '').trim() : '',
      device_id: deviceId,
      telemetry: probe.snapshot(hpEl ? hpEl.value : '')
    });
  };

  // Land focus on the first empty field so a returning user can start typing.
  setTimeout(() => {
    (userEl.value ? passEl : userEl).focus();
  }, 60);

  return () => probe.destroy();
}
"""
)

_login_component = st.components.v2.component(
    "reverie_login",
    html=_LOGIN_HTML,
    css=_LOGIN_CSS,
    js=_LOGIN_JS,
    isolate_styles=False,   # inherit the app's theme tokens
)


# ==============================================================================
# SESSION
# ==============================================================================


def current_user() -> Optional[store.User]:
    """The signed-in user, or ``None``. Expires stale sessions."""
    username = st.session_state.get(SESSION_USER)
    if not username:
        return None
    started = st.session_state.get(SESSION_STARTED, 0)
    if time.time() - started > SESSION_MAX_AGE_S:
        sign_out()
        return None
    return store.get_user(username)


def sign_out() -> None:
    for key in (SESSION_USER, SESSION_STARTED, SESSION_RISK, SESSION_PENDING):
        st.session_state.pop(key, None)


def _begin_session(user: store.User, assessment: scoring.RiskAssessment) -> None:
    st.session_state[SESSION_USER] = user.username
    st.session_state[SESSION_STARTED] = time.time()
    st.session_state[SESSION_RISK] = {
        "score": assessment.score,
        "band": assessment.band,
        "decision": assessment.decision,
        "reasons": assessment.reasons,
        "location": assessment.location.label if assessment.location else "",
        "at": time.time(),
    }


# ==============================================================================
# CONTEXT
# ==============================================================================


def _client_ip() -> str:
    """Client address from Streamlit's context, honouring proxy config."""
    try:
        headers = dict(st.context.headers or {})
    except Exception:
        headers = {}
    try:
        socket_ip = st.context.ip_address or ""
    except Exception:
        socket_ip = ""
    return geo.client_ip_from_headers(headers, fallback=socket_ip or "")


def _browser_timezone(telemetry: dict) -> str:
    tz = (telemetry or {}).get("timezone") or ""
    if tz:
        return tz
    try:
        return st.context.timezone or ""
    except Exception:
        return ""


# ==============================================================================
# SIGN-IN FLOW
# ==============================================================================


def _handle_signup(payload: dict, bot: scoring.BotAssessment,
                   device_id: str) -> Optional[str]:
    """Create an account, then sign the new user straight in.

    Bot detection has already run in :func:`_handle_submit` and runs *before*
    this is reached, which is the important ordering: a sign-up form is a more
    attractive automation target than a sign-in one, because a bot that gets
    through creates durable state rather than just failing a password check.

    Risk scoring is deliberately not applied here. It scores a sign-in against
    the account's own history, and a brand-new account has none - every signal
    it depends on (familiar device, familiar network, habitual hour, travel
    velocity) is undefined. Scoring it anyway would either flag every genuine
    new user or, worse, teach the model that "no history" means "low risk".
    The first *subsequent* sign-in is scored normally.
    """
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    confirm = payload.get("confirm") or ""
    display_name = (payload.get("display_name") or "").strip()

    if password != confirm:
        return "The two passwords do not match."

    try:
        user = store.create_user(username, password, display_name)
    except ValueError as exc:
        # store.create_user enforces length and uniqueness; surface its message
        # rather than a generic one, because on sign-up the user genuinely
        # needs to know which constraint they hit.
        return str(exc)

    location = geo.lookup(_client_ip()) if _client_ip() else geo.GeoLocation()

    store.record_event(
        user.username, success=True, decision="account_created",
        risk_score=0.0, bot_score=bot.score,
        location=location, device_id=device_id,
        reasons=["Account created"],
    )
    store.remember_device(user.username, device_id)
    store.update_user(user.username, last_login=time.time())

    # The device that created the account is trusted for this first session.
    assessment = scoring.RiskAssessment(
        score=0.0, decision=scoring.ALLOW, band=scoring.BAND_LOW,
        reasons=["New account created on this device"], location=location,
    )
    _begin_session(user, assessment)
    return None


def _handle_submit(payload: dict) -> Optional[str]:
    """Process one submission. Returns an error message, or ``None`` on success.

    Order matters here. Bot detection runs *before* the credential check so an
    automated client burns no scrypt work and gets no signal about whether the
    username exists. Credentials are then verified before the risk model runs,
    because risk scoring is only meaningful once we know whose account it is.
    """
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    device_id = (payload.get("device_id") or "").strip()
    telemetry = payload.get("telemetry") or {}

    signals = BotSignals.from_payload(telemetry)
    bot = scoring.score_bot(signals)

    mode = "signup" if payload.get("mode") == "signup" else "signin"

    if bot.is_bot:
        store.record_event(
            username, success=False, decision="deny",
            risk_score=0.0, bot_score=bot.score,
            location=geo.GeoLocation(), device_id=device_id,
            reasons=bot.reasons, hard_rules=bot.hard_rules,
        )
        # Deliberately vague. Naming the detector's reasons would tell an
        # attacker exactly which signal to fix next.
        return "We could not verify this request. Please reload the page and try again."

    if mode == "signup":
        return _handle_signup(payload, bot, device_id)

    user = store.authenticate(username, password)
    if user is None:
        store.record_event(
            username, success=False, decision="deny",
            risk_score=0.0, bot_score=bot.score,
            location=geo.GeoLocation(), device_id=device_id,
        )
        # Identical message for unknown user and wrong password, matching the
        # constant-time behaviour in store.authenticate().
        return "Incorrect username or password."

    ip = _client_ip()
    location = geo.lookup(ip) if ip else geo.GeoLocation()

    attempt = LoginAttempt(
        timestamp=time.time(),
        location=location,
        device_id=device_id,
        browser_timezone=_browser_timezone(telemetry),
        account_age_days=user.account_age_days,
        failed_attempts_1h=store.count_recent_failures(user.username),
        logins_24h=store.count_recent_attempts(user.username),
        history=store.get_login_history(user.username),
    )
    assessment = scoring.score_login(attempt)

    if assessment.decision == scoring.DENY:
        store.record_event(
            user.username, success=False, decision=assessment.decision,
            risk_score=assessment.score, bot_score=bot.score,
            location=location, device_id=device_id,
            reasons=assessment.reasons, hard_rules=assessment.hard_rules,
        )
        st.session_state[SESSION_PENDING] = {
            "username": user.username,
            "device_id": device_id,
            "assessment": assessment,
            "bot_score": bot.score,
        }
        return None  # the challenge screen takes over

    if assessment.decision == scoring.CHALLENGE:
        store.record_event(
            user.username, success=False, decision=assessment.decision,
            risk_score=assessment.score, bot_score=bot.score,
            location=location, device_id=device_id,
            reasons=assessment.reasons, hard_rules=assessment.hard_rules,
        )
        st.session_state[SESSION_PENDING] = {
            "username": user.username,
            "device_id": device_id,
            "assessment": assessment,
            "bot_score": bot.score,
        }
        return None

    store.record_event(
        user.username, success=True, decision=assessment.decision,
        risk_score=assessment.score, bot_score=bot.score,
        location=location, device_id=device_id,
        reasons=assessment.reasons, hard_rules=assessment.hard_rules,
    )
    store.remember_device(user.username, device_id)
    store.update_user(user.username, last_login=time.time())
    _begin_session(user, assessment)
    return None


def _render_challenge(pending: dict) -> None:
    """Step-up verification for an elevated-risk sign-in.

    A real deployment sends a code out of band - email, SMS, TOTP - and this is
    where that call belongs. The demo prints the code on screen and says so,
    rather than pretending to have sent an email it cannot send.
    """
    assessment: scoring.RiskAssessment = pending["assessment"]
    username = pending["username"]

    if "challenge_code" not in pending:
        pending["challenge_code"] = f"{secrets.randbelow(1000000):06d}"
        pending["attempts"] = 0
        st.session_state[SESSION_PENDING] = pending

    denied = assessment.decision == scoring.DENY
    tone = "var(--rv-neg)" if denied else "var(--rv-warn)"
    heading = "Sign-in blocked" if denied else "Additional verification required"

    reasons = "".join(
        f'<li style="margin-bottom:4px">{r}</li>' for r in assessment.reasons[:6]
    ) or "<li>Unusual sign-in pattern</li>"

    location = assessment.location.label if assessment.location else "Unknown location"

    st.html(f"""
    <div style="max-width:520px;margin:6vh auto 0;position:relative;z-index:5">
      <div class="rv-card" style="border-color:{tone}">
        <div class="rv-row" style="gap:10px;margin-bottom:14px">
          <span class="rv-pulse" style="background:{tone}"></span>
          <span style="font-size:var(--rv-fs-h3);font-weight:650;color:var(--rv-text)">
            {heading}
          </span>
        </div>
        <div style="font-size:var(--rv-fs-small);color:var(--rv-text-muted);
                    line-height:1.6;margin-bottom:14px">
          This sign-in to <strong style="color:var(--rv-text)">{username}</strong>
          from <strong style="color:var(--rv-text)">{location}</strong> scored
          <strong style="color:{tone}">{assessment.percent}%</strong> on our risk model.
        </div>
        <div class="rv-eyebrow" style="margin-bottom:6px">Why this was flagged</div>
        <ul style="margin:0 0 4px 18px;padding:0;font-size:var(--rv-fs-small);
                   color:var(--rv-text-muted);line-height:1.55">{reasons}</ul>
      </div>
    </div>
    """)

    with st.container():
        left, mid, right = st.columns([1, 2, 1])
        with mid:
            if denied:
                st.error(
                    "This attempt was blocked and recorded. If this was you, "
                    "verify with the code below to continue."
                )
            st.info(
                f"**Demo verification code: `{pending['challenge_code']}`**\n\n"
                "A production deployment sends this by email, SMS or an "
                "authenticator app. It is shown here because this demo has no "
                "mail transport configured."
            )
            code = st.text_input("Verification code", max_chars=6,
                                 key="challenge_code_input",
                                 placeholder="000000")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Verify", type="primary", width="stretch"):
                    if code.strip() == pending["challenge_code"]:
                        user = store.get_user(username)
                        if user:
                            store.record_event(
                                username, success=True, decision="challenge_passed",
                                risk_score=assessment.score,
                                bot_score=pending.get("bot_score", 0.0),
                                location=assessment.location or geo.GeoLocation(),
                                device_id=pending["device_id"],
                                reasons=["Step-up verification passed"],
                            )
                            store.remember_device(username, pending["device_id"])
                            store.update_user(username, last_login=time.time())
                            _begin_session(user, assessment)
                            st.session_state.pop(SESSION_PENDING, None)
                            st.rerun()
                    else:
                        pending["attempts"] = pending.get("attempts", 0) + 1
                        st.session_state[SESSION_PENDING] = pending
                        if pending["attempts"] >= 3:
                            st.session_state.pop(SESSION_PENDING, None)
                            st.error("Too many incorrect codes. Start again.")
                            time.sleep(1.2)
                            st.rerun()
                        else:
                            st.error(
                                f"Incorrect code. "
                                f"{3 - pending['attempts']} attempts remaining."
                            )
            with c2:
                if st.button("Cancel", width="stretch"):
                    st.session_state.pop(SESSION_PENDING, None)
                    st.rerun()


def render_login(active_theme: theme_mod.Theme) -> None:
    """Draw the sign-in screen. Call only when nobody is signed in."""
    st.html(theme_mod.build_css(active_theme))
    fx.mount(active_theme)
    fx.mount_backdrop(active_theme, particles=True, grain=True)

    pending = st.session_state.get(SESSION_PENDING)
    if pending:
        _render_challenge(pending)
        return

    error = st.session_state.pop("auth_error", None)

    result = _login_component(
        data={"device_salt": _DEVICE_SALT, "error": error or ""},
        on_submit_change=lambda: None,
    )

    if result.submit:
        message = _handle_submit(result.submit)
        if message:
            st.session_state["auth_error"] = message
        st.rerun()



def require_login(active_theme: theme_mod.Theme) -> Optional[store.User]:
    """Gate the app. Returns the user, or ``None`` if the login screen was drawn.

    Callers must stop rendering when this returns ``None``.
    """
    user = current_user()
    if user is not None:
        # A live session outranks any half-finished challenge left in state.
        st.session_state.pop(SESSION_PENDING, None)
        return user
    render_login(active_theme)
    return None
