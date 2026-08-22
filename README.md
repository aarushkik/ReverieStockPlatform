# Reverie Terminal

A market terminal with a verifiable AI research layer: live quotes, screeners,
technical research, a paper-trading simulator — and a **Workbench** where AI
analysis runs as an auditable workflow instead of a chat.

## The idea

> Every AI answer in finance is a black box you cannot audit. Reverie turns AI
> research into a workflow where every claim carries a receipt.

Pick a workflow, watch it execute as a DAG over real market-data tools, and get
a memo in which every number is a citation back to the exact tool call, source
and timestamp that measured it. If a data source fails, the run goes red and
**refuses to produce the memo** rather than letting the model write around the
gap.

Asking a model to cite its sources is easy and worth little — it will attach a
plausible citation to a number it invented. The verifier re-reads the finished
memo, extracts every numeric claim, and checks it against the fact it cites.
Four outcomes, each surfaced in the UI:

| | |
| --- | --- |
| `verified` | the figure matches what was measured (rounding allowed) |
| `uncited` | a number with no source |
| `unknown_fact` | cites an id that is not in the ledger |
| `mismatch` | cites a real fact but states a different number |

## Running it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m auth.train      # trains the two security models (~30s)
streamlit run app.py
```

The first run has no accounts, so the sign-in screen offers to create one.
Set any one of `FEATHERLESS_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
`DEEPSEEK_API_KEY` or `GEMINI_API_KEY` to enable memo writing; without one the
Workbench still runs and collects facts, and says so.

## Layout

| Path | What it is |
| --- | --- |
| `app.py` | The terminal: tabs, layout, charts |
| `workflow/` | The Workbench — tool registry, DAG engine, fact ledger, citation verifier, templates |
| `theme.py` | Design tokens — the single source of truth for every colour, size and spacing value |
| `ui_effects.py` | Motion primitives ported from React Bits |
| `indicators.py` | Technical indicators (pure, tested) |
| `marketdata.py` | Market data fetching that raises instead of inventing |
| `predictive_model.py` | Direction classifier over engineered features |
| `auth/` | Sign-in, login-risk scoring, bot detection |
| `tests/` | 151 tests, no network, ~1s |

## What this app will not do

It will not show you a number it did not measure. That sounds obvious; it was
not true of this codebase until recently, and the fixes are the reason the
Workbench's claim is credible:

- `get_ticker_info` invented a whole company on failure — market cap $250B,
  P/E 24.5, EPS 4.5 — and derived the day's change from
  `sum(ord(c) for c in symbol)`, the arithmetic of the ticker's letters.
- `get_market_scanners` rebuilt the entire movers table from that same
  character-sum whenever fewer than five symbols resolved.
- `get_recent_insiders` returned ten fabricated transactions attributed to
  real, named executives, with dates stamped relative to `now()` so they always
  looked fresh. It made no network call at all.
- `process_advanced_analytics` returned RSI exactly 50, a quant score of
  exactly 50, and support/resistance off a $150.00 placeholder when it had too
  little history.
- `predictive_model` reported a **58.5% backtest accuracy** that was never
  computed, plus five hardcoded feature importances, whenever training failed.
- `chat_with_ai_copilot` returned a canned sentence styled as analysis when
  every LLM provider failed.
- RSS news had been failing on *every* request — `urllib` could not verify TLS
  against the system trust store, and a bare `except` turned that into an empty
  list, indistinguishable from a market with no headlines.

All of it is gone. Unmeasured values render as an em dash; failed fetches raise;
partial coverage is reported ("3 of 4 symbols resolved") rather than topped up.

## Design system

Nothing hardcodes a colour. `theme.py` resolves a `Theme` into CSS custom
properties for markup and Python values for Plotly, which renders server-side
and cannot read CSS variables. Palette × accent × density × radius × motion —
648 combinations, all verified to build — plus colour-vision-deficiency
alternatives for the gain/loss pair, live-editable and saveable to the account.

Contrast is enforced, not hoped for: `ensure_contrast()` walks any colour toward
black or white until it clears 4.5:1 against its surface, so Cyan on the light
palette resolves to `#147F8F` while staying recognisably cyan.

## Security

Sign-in runs bot detection, then credentials, then risk scoring — in that order,
so an automated client burns no password-hashing work and learns nothing about
which usernames exist. The outcome is graded: allow, challenge, or deny.

Login risk uses 18 features including implied travel velocity between
consecutive sign-ins; bot detection uses 19 including pointer path straightness
and keystroke rhythm. Deterministic rules outrank the model in both directions —
a journey requiring Mach 5 is not a probability, and a filled honeypot is proof.

**Both models are trained on simulated data**, because no labelled corpus of
real sign-ins exists here. The reported metrics measure how well each model
recovers its own generator, not field accuracy against a live adversary. This is
stated in the code, the model cards, and on the Security tab.

| | Login risk | Bot detection |
| --- | --- | --- |
| ROC-AUC | 0.966 | 0.978 |
| Precision / Recall | 0.926 / 0.941 | 0.976 / 0.969 |
| False-positive rate | 0.048 | 0.018 |

## Configuration

- `FINNHUB_API_KEY` — live quotes
- `TRUST_PROXY_HEADERS` — set only behind a proxy you control.
  `X-Forwarded-For` is client-controllable; trusting it on a directly exposed
  server lets an attacker choose which country they appear to be in.
- `DEVICE_ID_SALT` — salts the device fingerprint per deployment

`auth/data/` holds account records and the sign-in log. It is gitignored.
