# Reverie Terminal

A Streamlit market terminal: live quotes, heatmaps, screeners, technical
research, a paper-trading simulator and an AI copilot — behind a sign-in that
scores every attempt with a trained risk model.

## Running it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m auth.train      # trains the two security models (~30s)
streamlit run app.py
```

The first run has no accounts, so the sign-in screen offers to create one.

## Layout

| Path | What it is |
| --- | --- |
| `app.py` | The terminal: tabs, data fetching, charts |
| `theme.py` | Design tokens — the single source of truth for every colour, size and spacing value |
| `ui_effects.py` | Motion primitives ported from React Bits |
| `auth/` | Sign-in, login risk scoring, bot detection |
| `data_fetcher.py`, `analyzer.py`, `agent_logic.py`, `dashboard.py` | Market data and analysis backend |

## Design system

Nothing in the app hardcodes a colour. `theme.py` resolves a `Theme` into CSS
custom properties for markup and plain Python values for Plotly, which renders
server-side and cannot read CSS variables.

Tokens vary along independent axes, so they compose — 648 combinations, all
verified to build:

- **palette** — Midnight, Graphite, Abyss, Parchment (light)
- **accent** — Mint, Azure, Violet, Amber, Rose, Cyan
- **density** — Compact / Cozy / Roomy (spacing, control and row heights)
- **radius**, **motion**, **text scale**, glass, grid lines, small caps
- **gain/loss pair** — including colour-vision-deficiency alternatives

All of it is live-editable from **Appearance** in the sidebar and saveable to
the account.

Contrast is enforced rather than hoped for. `ensure_contrast()` walks any
colour toward black or white until it clears 4.5:1 against the surface it sits
on, so an accent tuned for a dark palette stays legible on the light one —
Cyan on Parchment resolves to `#147F8F` while staying recognisably cyan. Text
colours are split from fill colours, since the contrast floor applies to type
but would wash out large fills and chart series.

## Motion

Effects are ports of [React Bits](https://reactbits.dev) components
(MIT + Commons Clause) rewritten as framework-free CSS and DOM script, because
this app renders server-side and adopting the React originals would mean
shipping a component bundle for every animated number on the page.

`SpotlightCard`, `CountUp`, `ShinyText`, `GradientText`, `DecryptedText`,
`ClickSpark`, `StarBorder`, `AnimatedContent`, `Magnet`, and an
Aurora + Particles backdrop for the sign-in screen.

CountUp keeps upstream's spring constants and integrates them directly, so the
curve matches the Framer Motion original. Everything degrades to its finished
state — a counter that never binds still shows the correct figure — and every
effect honours both the motion token and the OS reduce-motion setting.

## Security

Sign-in runs three checks in order: **bot detection** (so automated clients
burn no password-hashing work and learn nothing about which usernames exist),
**credentials**, then **risk scoring**.

The outcome is graded — allow, challenge, or deny — because locking a trader
out of their own account is worse than asking for a second factor.

**Login risk** combines 18 features: implied travel velocity between
consecutive sign-ins, distance, elapsed time, country/city/network/device
familiarity, hour-of-day deviation measured on the circle, datacenter and
proxy reputation, recent failures, account age, and browser-vs-IP timezone
agreement.

**Bot detection** uses 19 features from a browser probe: pointer path
straightness and turn-angle entropy, keystroke rhythm, form fill time,
automation flags, environment plausibility, and a honeypot field.

Deterministic rules outrank the model in both directions. A journey requiring
Mach 5 is not a probability, and a filled honeypot is proof rather than
evidence; equally, a known device on a known network de-escalates, because
over-challenging trains people to click through prompts without reading them.
Every decision carries plain-language reasons — an unexplained risk score is
unactionable for the user and unauditable afterwards.

Passwords are scrypt hashes with per-user salts. Unknown usernames still run a
full scrypt computation against a decoy, so timing cannot enumerate accounts.
The event log stores resolved city and coarse coordinates, never the raw IP.

### On the models

**Both models are trained on simulated data**, because no labelled corpus of
real sign-ins exists for this application. The reported metrics measure how
well each model recovers its own generator — they are not an estimate of field
accuracy against a live adversary. This is stated in the code, in the model
cards, and on the Security tab.

| | Login risk | Bot detection |
| --- | --- | --- |
| ROC-AUC | 0.966 | 0.978 |
| PR-AUC | 0.941 | 0.966 |
| Brier | 0.046 | 0.022 |
| Calibration error | 0.018 | 0.005 |
| Precision / Recall | 0.926 / 0.941 | 0.976 / 0.969 |
| False-positive rate | 0.048 | 0.018 |

Probabilities are isotonically calibrated, because the gate compares them
against a threshold and so they have to mean something. The threshold is
chosen against a cost model rather than accuracy.

The generators deliberately overlap the classes — a first version scored
AUC 1.000, which meant the classes were trivially separable and the models had
learned a giveaway. They now include the cases real systems get wrong:
business travellers on new devices, users who fumble a password, attackers on
residential proxies, stolen device fingerprints, password-manager autofill and
keyboard-only navigation. Residual error concentrates in exactly those
ambiguous scenarios and is 0% on the unambiguous ones.

Every real sign-in is logged in the same schema the generator emits, so
retraining on genuine data is a change of source, not a rewrite:

```bash
python -m auth.train
```

## Configuration

Optional, via `.env` or environment:

- `FINNHUB_API_KEY` — live quotes
- `TRUST_PROXY_HEADERS` — set only when behind a proxy you control.
  `X-Forwarded-For` is client-controllable; trusting it on a directly exposed
  server lets an attacker choose which country they appear to be in.
- `DEVICE_ID_SALT` — salts the device fingerprint per deployment

`auth/data/` holds account records and the sign-in log. It is gitignored and
should stay that way.
