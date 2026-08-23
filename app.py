import os
import time
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import urllib.request
import requests

# Import backend engine
from data_fetcher import get_stock_data, load_env_file
from analyzer import run_analysis, analyze_sentiment
from agent_logic import evaluate_ticker
from dashboard import generate_markdown_report

# Design system, motion primitives and the authentication layer
import indicators
import marketdata
import theme as theme_mod
import ui_effects as fx
import workflow as wf
from workflow import llm as wf_llm, render as wf_render
from theme import rgba, value_color
from auth import scoring as risk_scoring, store as auth_store, ui as auth_ui


# Custom React component for Order Entry using CCv2
_REACT_ORDER_DESK = st.components.v2.component(
    "react_order_desk",
    html="""
    <div id="react-root"></div>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/react@18/umd/react.production.min.js" crossorigin></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js" crossorigin></script>
    <script src="https://unpkg.com/htm@3.1.1/dist/htm.umd.js" crossorigin></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css"/>
    <style>
        body {
            margin: 0;
            padding: 0;
            background: transparent !important;
        }
        /* Custom styled number input spinner hide */
        input[type=number]::-webkit-inner-spin-button, 
        input[type=number]::-webkit-outer-spin-button { 
            -webkit-appearance: none; 
            margin: 0; 
        }
    </style>
    """,
    js="""
    export default function (component) {
        const { data, parentElement, setStateValue, setTriggerValue } = component;
        const rootEl = parentElement.querySelector('#react-root');
        if (!rootEl) return;
        
        function initApp() {
            if (!window.React || !window.ReactDOM || !window.htm) {
                setTimeout(initApp, 30);
                return;
            }
            
            const React = window.React;
            const ReactDOM = window.ReactDOM;
            const html = window.htm.bind(React.createElement);
            
            const App = () => {
                const [orderType, setOrderType] = React.useState(data.trade_order_type || "BUY");
                const [qty, setQty] = React.useState(1);
                const [ticker, setTicker] = React.useState(data.active_ticker || "AAPL");
                
                const sp = data.live_price || 0.0;
                const et = sp * qty;
                
                React.useEffect(() => {
                    if (data.active_ticker && data.active_ticker !== ticker) {
                        setTicker(data.active_ticker);
                    }
                }, [data.active_ticker]);
                
                const handleExecute = () => {
                    setTriggerValue("execute_trade", {
                        ticker: ticker,
                        type: orderType,
                        quantity: qty,
                        price: sp
                    });
                };
                
                const handleTickerChange = (val) => {
                    const upperVal = val.toUpperCase();
                    setTicker(upperVal);
                    setStateValue("active_ticker", upperVal);
                };
                
                return html`
                    <div style="background-color: var(--rv-surface); border: 1px solid var(--rv-border); border-radius: 8px; padding: 20px; font-family: 'Inter', -apple-system, sans-serif; color: var(--rv-text);">
                        <h2 style="font-size: 13px; font-weight: 800; color: var(--rv-text-muted); text-transform: uppercase; letter-spacing: 0.8px; margin-top: 0; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid var(--rv-border);">Simulation Order Desk</h2>
                        
                        <!-- Ticker Symbol -->
                        <div style="margin-bottom: 16px;">
                            <label style="display: block; font-size: 11px; font-weight: 700; color: var(--rv-text-muted); text-transform: uppercase; margin-bottom: 6px;">Ticker Symbol</label>
                            <input 
                                type="text" 
                                value=${ticker} 
                                onChange=${(e) => handleTickerChange(e.target.value)}
                                style="width: 100%; box-sizing: border-box; background-color: var(--rv-surface-alt); border: 1px solid var(--rv-border); color: var(--rv-text); font-size: 14px; border-radius: 4px; padding: 10px; outline: none; font-weight: 700; text-transform: uppercase; transition: border-color 0.2s;"
                                onFocus=${(e) => e.target.style.borderColor = 'var(--rv-pos)'}
                                onBlur=${(e) => e.target.style.borderColor = 'var(--rv-border)'}
                            />
                        </div>
                        
                        <!-- BUY/SELL Toggles -->
                        <div style="margin-bottom: 16px;">
                            <label style="display: block; font-size: 11px; font-weight: 700; color: var(--rv-text-muted); text-transform: uppercase; margin-bottom: 6px;">Transaction Type</label>
                            <div style=${{
                                display: "grid",
                                gridTemplateColumns: "1fr 1fr",
                                gap: "8px",
                                backgroundColor: "var(--rv-surface-alt)",
                                padding: "4px",
                                borderRadius: "4px",
                                border: "1px solid " + (orderType === "BUY" ? "var(--rv-pos)" : "var(--rv-neg)")
                            }}>
                                <button 
                                    type="button"
                                    onClick=${() => {
                                        setOrderType("BUY");
                                        setStateValue("trade_order_type", "BUY");
                                    }}
                                    style=${{
                                        padding: "10px 0",
                                        borderRadius: "4px",
                                        fontWeight: "800",
                                        fontSize: "13px",
                                        cursor: "pointer",
                                        border: "none",
                                        transition: "all 0.2s",
                                        backgroundColor: orderType === "BUY" ? "var(--rv-pos)" : "transparent",
                                        color: orderType === "BUY" ? "var(--rv-bg)" : "var(--rv-text-muted)",
                                        boxShadow: orderType === "BUY" ? "0 0 14px rgba(0, 230, 118, 0.4)" : "none"
                                    }}
                                >
                                    BUY
                                </button>
                                <button 
                                    type="button"
                                    onClick=${() => {
                                        setOrderType("SELL");
                                        setStateValue("trade_order_type", "SELL");
                                    }}
                                    style=${{
                                        padding: "10px 0",
                                        borderRadius: "4px",
                                        fontWeight: "800",
                                        fontSize: "13px",
                                        cursor: "pointer",
                                        border: "none",
                                        transition: "all 0.2s",
                                        backgroundColor: orderType === "SELL" ? "var(--rv-neg)" : "transparent",
                                        color: orderType === "SELL" ? "var(--rv-text)" : "var(--rv-text-muted)",
                                        boxShadow: orderType === "SELL" ? "0 0 14px rgba(255, 23, 68, 0.4)" : "none"
                                    }}
                                >
                                    SELL
                                </button>
                            </div>
                        </div>
                        
                        <!-- Share Count -->
                        <div style="margin-bottom: 16px;">
                            <label style="display: block; font-size: 11px; font-weight: 700; color: var(--rv-text-muted); text-transform: uppercase; margin-bottom: 6px;">Share Count</label>
                            <input 
                                type="number" 
                                min="1" 
                                value=${qty} 
                                onChange=${(e) => setQty(Math.max(1, parseInt(e.target.value) || 1))}
                                style="width: 100%; box-sizing: border-box; background-color: var(--rv-surface-alt); border: 1px solid var(--rv-border); color: var(--rv-text); font-size: 14px; border-radius: 4px; padding: 10px; outline: none; font-weight: 700;"
                            />
                        </div>
                        
                        <!-- Unit Price & Est Total -->
                        <div style="background-color: var(--rv-surface-alt); border: 1px solid var(--rv-border); border-radius: 4px; padding: 12px; font-size: 12px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                            <div>
                                <span style="color: var(--rv-text-muted);">Unit Price:</span>
                                <strong style="color: var(--rv-text); margin-left: 6px; font-family: 'JetBrains Mono', monospace; font-size: 13px;">$${sp.toFixed(2)}</strong>
                            </div>
                            <div>
                                <span style="color: var(--rv-text-muted);">Est Total:</span>
                                <strong style=${{
                                    color: orderType === 'BUY' ? 'var(--rv-pos)' : 'var(--rv-neg)',
                                    marginLeft: '6px',
                                    fontFamily: "'JetBrains Mono', monospace",
                                    fontSize: "13px"
                                }}>$${et.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</strong>
                            </div>
                        </div>
                        
                        <!-- Submit button -->
                        <button 
                            type="button"
                            onClick=${handleExecute}
                            disabled=${sp === 0}
                            style=${{
                                width: "100%",
                                padding: "12px 0",
                                borderRadius: "4px",
                                fontWeight: "900",
                                fontSize: "13px",
                                textTransform: "uppercase",
                                trackingWider: "1.2px",
                                cursor: sp === 0 ? "not-allowed" : "pointer",
                                border: "none",
                                transition: "all 0.25s",
                                backgroundColor: sp === 0 ? "var(--rv-border)" : (orderType === "BUY" ? "var(--rv-pos)" : "var(--rv-neg)"),
                                color: sp === 0 ? "var(--rv-text-muted)" : (orderType === "BUY" ? "var(--rv-bg)" : "var(--rv-text)"),
                                boxShadow: sp === 0 ? "none" : (orderType === "BUY" ? "0 4px 15px rgba(0, 230, 118, 0.3)" : "0 4px 15px rgba(255, 23, 68, 0.3)")
                            }}
                        >
                            Execute ${orderType} Order
                        </button>
                    </div>
                `;
            };
            
            if (!window.reactRoots) window.reactRoots = new WeakMap();
            let root = window.reactRoots.get(rootEl);
            if (!root) {
                root = ReactDOM.createRoot(rootEl);
                window.reactRoots.set(rootEl, root);
            }
            root.render(React.createElement(App));
        }
        
        initApp();
    }
    """
)

# ==============================================================================
# STREAMLIT PAGE CONFIGURATION
# ==============================================================================
def load_env_file():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        if key.strip() not in os.environ:
                            os.environ[key.strip()] = val.strip()
        except Exception:
            pass

load_env_file()


def _load_streamlit_secrets() -> None:
    """Copy st.secrets into os.environ.

    Everything in this codebase reads configuration with os.environ.get, which
    works locally because load_env_file() populates it from .env. On Streamlit
    Community Cloud there is no .env: secrets are pasted into the dashboard and
    surfaced as st.secrets instead. Without this bridge a deployed instance
    would silently behave as though no API key had been set, which is exactly
    the kind of quiet misconfiguration that is hard to diagnose from a running
    app.

    Existing environment variables win, so a local .env still overrides.
    """
    try:
        secrets = st.secrets
    except Exception:
        # No secrets.toml locally and no Cloud secrets configured. Not an error.
        return
    try:
        items = list(secrets.items())
    except Exception:
        return
    for key, value in items:
        if isinstance(value, (str, int, float, bool)) and not os.environ.get(str(key)):
            os.environ[str(key)] = str(value)


_load_streamlit_secrets()

st.set_page_config(
    page_title="Reverie Terminal",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==============================================================================
# APPEARANCE
# ==============================================================================
# Every visual token lives in theme.py. This block only resolves the user's
# saved preferences into a Theme and installs the resulting stylesheet; nothing
# below should hardcode a colour, a font size or a spacing value.

APPEARANCE_DEFAULTS = {
    "palette": "midnight",
    "accent": "mint",
    "density": "cozy",
    "radius": "soft",
    "motion": "full",
    "cvd": "classic",
    "type_scale": 1.0,
    "glass": True,
    "grid_lines": True,
    "uppercase_labels": True,
    "effects": True,
}

# Preferences are held in one plain dict, deliberately *not* under the
# appearance widgets' own keys.
#
# Streamlit garbage-collects the session-state entry of any keyed widget that
# was not instantiated on the previous run. The sidebar does not render on the
# sign-in run (the script stops at the auth gate), so widget-owned values were
# being purged and re-seeded from defaults on the very next run - which is why
# a saved palette applied for exactly one frame and then snapped back to
# Midnight. A non-widget key is not subject to that collection.
if "appearance" not in st.session_state:
    st.session_state["appearance"] = dict(APPEARANCE_DEFAULTS)


def pref(name):
    return st.session_state["appearance"].get(name, APPEARANCE_DEFAULTS[name])


def _commit_pref(name: str) -> None:
    """Copy a sidebar widget's value into the canonical dict."""
    st.session_state["appearance"][name] = st.session_state[f"ui_{name}"]


def active_theme() -> theme_mod.Theme:
    """Resolve the current appearance preferences into a Theme."""
    return theme_mod.Theme(
        palette_key=pref("palette"),
        accent_key=pref("accent"),
        density_key=pref("density"),
        radius_key=pref("radius"),
        motion_key=pref("motion"),
        cvd_key=pref("cvd"),
        type_scale=pref("type_scale"),
        glass=pref("glass"),
        grid_lines=pref("grid_lines"),
        uppercase_labels=pref("uppercase_labels"),
    )


T = active_theme()
st.html(theme_mod.build_css(T))

# ==============================================================================
# AUTHENTICATION GATE
# ==============================================================================
# Nothing below this point renders until a session exists. require_login draws
# the sign-in screen itself and returns None, so the script must stop here
# rather than fall through to the terminal.

CURRENT_USER = auth_ui.require_login(T)
if CURRENT_USER is None:
    st.stop()

# Restore this user's saved appearance on the first run after sign-in, so
# preferences follow the account rather than the browser tab.
if not st.session_state.get("_appearance_restored"):
    _saved = (CURRENT_USER.preferences or {}).get("appearance") or {}
    st.session_state["appearance"].update(
        {k: v for k, v in _saved.items() if k in APPEARANCE_DEFAULTS}
    )
    st.session_state["_appearance_restored"] = True
    T = active_theme()
    # A second stylesheet for this run only; later rules win the cascade. From
    # the next run the theme is resolved correctly at the top of the script.
    st.html(theme_mod.build_css(T))

PLOTLY_LAYOUT = theme_mod.plotly_layout(T)

# ==============================================================================
# SESSION STATE & ROUTING
# ==============================================================================
_SESSION_DEFAULTS = {
    "current_tab": "MARKET_HOME",
    "active_ticker": "AAPL",
    "highlighted_pattern": "",
    "results": [],
    "portfolio_cash": 100000.00,
    "portfolio_holdings": {},
    "portfolio_history": [],
    "trade_order_type": "BUY",
    "wb_run": None,
}
for _key, _default in _SESSION_DEFAULTS.items():
    st.session_state.setdefault(_key, _default)

TABS = [
    ("MARKET_HOME", "Markets", "▤"),
    ("AI_COPILOT", "Copilot", "◈"),
    ("NEWS", "News", "▦"),
    ("MARKETS", "Screener", "▩"),
    ("RESEARCH", "Research", "◉"),
    ("WORKBENCH", "Workbench", "◆"),
    ("TRADE_DESK", "Simulator", "▧"),
    ("PATTERN_GUIDE", "Patterns", "◎"),
    ("SECURITY", "Security", "⬡"),
]
_TAB_IDS = {tid for tid, _, _ in TABS}


def go_to(tab_id: str, ticker: str = "") -> None:  # noqa: E302
    """Switch tabs in place.

    Navigation used to be anchor links to /?tab=X, which made every tab change
    a full page reload: the whole Streamlit session was torn down and rebuilt,
    every cache warmed from cold, and the browser flashed white in between.
    Mutating session state and rerunning keeps caches and scroll position.
    """
    if tab_id in _TAB_IDS:
        st.session_state["current_tab"] = tab_id
    if ticker:
        symbol = ticker.strip().upper()
        st.session_state["active_ticker"] = symbol
        # The nav symbol box is a keyed widget, and Streamlit ignores a keyed
        # widget's `value=` on every run after the first - its session-state
        # entry wins. Without this the box kept showing the old symbol while
        # the rest of the app had already moved on, so clicking SLB in a
        # scanner left "AAPL" in the field. Safe to assign here because every
        # caller runs before the widget is instantiated.
        st.session_state["nav_ticker_input"] = symbol


# Deep links are still honoured, but only on first load - once consumed the
# parameters are cleared so a later rerun does not yank the user back.
if st.query_params and not st.session_state.get("_query_consumed"):
    _params = st.query_params
    _tab = _params.get("tab", "")
    if _tab in ("AI_AGENT_RESEARCH", "AI AGENT RESEARCH"):
        _tab = "RESEARCH"
    if _tab in _TAB_IDS:
        st.session_state["current_tab"] = _tab
    if _params.get("ticker"):
        st.session_state["active_ticker"] = _params["ticker"].strip().upper()
        st.session_state["current_tab"] = "RESEARCH"
    st.session_state["_query_consumed"] = True
    st.query_params.clear()

# The chrome component installs the motion runtime and carries the ticker
# click bus back from the page. Mounted after go_to() is defined because a
# click arriving on this run navigates immediately.
if pref("effects"):
    _chrome = fx.mount(T)
    _click = getattr(_chrome, "ticker", None)
    if _click:
        go_to(_click.get("dest") or "RESEARCH", ticker=_click.get("symbol", ""))
        st.rerun()

# A tab id persisted by an older build (or a hand-edited query param) must not
# leave the app on a branch that no longer exists. _TAB_IDS is derived from TABS,
# so this cannot drift the way a hand-maintained set does.
if st.session_state.get("current_tab") not in _TAB_IDS:
    st.session_state["current_tab"] = "MARKET_HOME"

current_tab = st.session_state["current_tab"]

# ==============================================================================
# TOP NAVIGATION
# ==============================================================================
# Two rows: identity and context on top, the tab row on its own line below.
# Sharing one line left roughly 120px per tab once a ninth was added, which
# clipped every label to an ellipsis.
_brand_col, _sym_col, _user_col = st.columns([4, 1.1, 0.9], vertical_alignment="center")

with _brand_col:
    st.html(
        '<div class="rv-row" style="gap:9px">'
        '<span style="width:24px;height:24px;border-radius:6px;'
        'background:var(--rv-accent-fill);color:var(--rv-on-accent);'
        'display:flex;align-items:center;justify-content:center;'
        'font-weight:800;font-size:13px">R</span>'
        '<span style="font-weight:650;font-size:var(--rv-fs-body);'
        'color:var(--rv-text);letter-spacing:-.01em">Reverie</span>'
        '<span style="font-size:var(--rv-fs-small);color:var(--rv-text-faint);'
        'margin-left:4px">terminal</span></div>'
    )

with _sym_col:
    st.session_state.setdefault("nav_ticker_input", st.session_state["active_ticker"])
    _typed = st.text_input(
        "Symbol",
        key="nav_ticker_input",
        label_visibility="collapsed",
        placeholder="Symbol",
    )
    if _typed and _typed.strip().upper() != st.session_state["active_ticker"]:
        st.session_state["active_ticker"] = _typed.strip().upper()

with _user_col:
    with st.popover(f"\u25d0  {CURRENT_USER.display_name.split()[0][:9]}", width="stretch"):
        st.markdown(f"**{CURRENT_USER.display_name}**")
        st.caption(f"@{CURRENT_USER.username}")
        _risk = st.session_state.get(auth_ui.SESSION_RISK) or {}
        if _risk:
            _band_color = {
                "low": "var(--rv-pos)",
                "elevated": "var(--rv-warn)",
                "high": "var(--rv-neg)",
            }.get(_risk.get("band", "low"), "var(--rv-text-muted)")
            st.html(
                f'<div class="rv-eyebrow" style="margin-top:6px">This session</div>'
                f'<div style="font-size:var(--rv-fs-small);color:var(--rv-text-muted);'
                f'line-height:1.5">Risk '
                f'<strong style="color:{_band_color}">'
                f'{int(_risk.get("score", 0) * 100)}%</strong>'
                f' \u00b7 {_risk.get("location") or "Unknown location"}</div>'
            )
        st.divider()
        if st.button("Sign out", key="sign_out_btn", width="stretch"):
            auth_ui.sign_out()
            st.rerun()

for _col, (_tid, _label, _glyph) in zip(st.columns(len(TABS)), TABS):
    with _col:
        _col.button(
            f"{_glyph} {_label}",
            key=f"nav_{_tid}",
            on_click=go_to,
            args=(_tid,),
            type="primary" if current_tab == _tid else "secondary",
            width="stretch",
        )

st.html('<div style="height:1px;background:var(--rv-border);margin:2px 0 10px"></div>')


# ==============================================================================
# HELPERS & DATA UTILITIES
# ==============================================================================
HEATMAP_STOCKS = {
    # Technology
    "AAPL": {"sector": "Technology", "cap": 3000e9},
    "MSFT": {"sector": "Technology", "cap": 3100e9},
    "NVDA": {"sector": "Technology", "cap": 2900e9},
    "AVGO": {"sector": "Technology", "cap": 750e9},
    "QCOM": {"sector": "Technology", "cap": 220e9},
    "TXN": {"sector": "Technology", "cap": 180e9},
    "AMD": {"sector": "Technology", "cap": 240e9},
    "INTC": {"sector": "Technology", "cap": 150e9},
    "MU": {"sector": "Technology", "cap": 120e9},
    "ADI": {"sector": "Technology", "cap": 90e9},
    "LRCX": {"sector": "Technology", "cap": 110e9},
    "AMAT": {"sector": "Technology", "cap": 140e9},
    "CRM": {"sector": "Technology", "cap": 260e9},
    "ORCL": {"sector": "Technology", "cap": 480e9},
    "PANW": {"sector": "Technology", "cap": 100e9},
    "FTNT": {"sector": "Technology", "cap": 50e9},
    "CSCO": {"sector": "Technology", "cap": 200e9},
    "ADSK": {"sector": "Technology", "cap": 50e9},
    "PLTR": {"sector": "Technology", "cap": 70e9},
    "ANET": {"sector": "Technology", "cap": 90e9},
    # Consumer Cyclical
    "AMZN": {"sector": "Consumer Cyclical", "cap": 1900e9},
    "TSLA": {"sector": "Consumer Cyclical", "cap": 800e9},
    "HD": {"sector": "Consumer Cyclical", "cap": 360e9},
    "LOW": {"sector": "Consumer Cyclical", "cap": 130e9},
    "NKE": {"sector": "Consumer Cyclical", "cap": 120e9},
    "SBUX": {"sector": "Consumer Cyclical", "cap": 90e9},
    "TJX": {"sector": "Consumer Cyclical", "cap": 100e9},
    "BKNG": {"sector": "Consumer Cyclical", "cap": 130e9},
    "F": {"sector": "Consumer Cyclical", "cap": 48e9},
    "GM": {"sector": "Consumer Cyclical", "cap": 54e9},
    # Communication Services
    "META": {"sector": "Communication Services", "cap": 1200e9},
    "GOOGL": {"sector": "Communication Services", "cap": 2100e9},
    "NFLX": {"sector": "Communication Services", "cap": 290e9},
    "DIS": {"sector": "Communication Services", "cap": 170e9},
    "T": {"sector": "Communication Services", "cap": 120e9},
    "VZ": {"sector": "Communication Services", "cap": 160e9},
    "TMUS": {"sector": "Communication Services", "cap": 220e9},
    "EA": {"sector": "Communication Services", "cap": 38e9},
    # Financials
    "JPM": {"sector": "Financials", "cap": 600e9},
    "BAC": {"sector": "Financials", "cap": 320e9},
    "WFC": {"sector": "Financials", "cap": 210e9},
    "MS": {"sector": "Financials", "cap": 150e9},
    "GS": {"sector": "Financials", "cap": 160e9},
    "C": {"sector": "Financials", "cap": 110e9},
    "AXP": {"sector": "Financials", "cap": 170e9},
    "BLK": {"sector": "Financials", "cap": 120e9},
    "BX": {"sector": "Financials", "cap": 140e9},
    "SCHW": {"sector": "Financials", "cap": 130e9},
    "V": {"sector": "Financials", "cap": 500e9},
    "MA": {"sector": "Financials", "cap": 420e9},
    # Healthcare
    "LLY": {"sector": "Healthcare", "cap": 800e9},
    "UNH": {"sector": "Healthcare", "cap": 520e9},
    "JNJ": {"sector": "Healthcare", "cap": 380e9},
    "ABBV": {"sector": "Healthcare", "cap": 300e9},
    "MRK": {"sector": "Healthcare", "cap": 280e9},
    "ABT": {"sector": "Healthcare", "cap": 190e9},
    "TMO": {"sector": "Healthcare", "cap": 210e9},
    "PFE": {"sector": "Healthcare", "cap": 160e9},
    "ISRG": {"sector": "Healthcare", "cap": 140e9},
    "CVS": {"sector": "Healthcare", "cap": 90e9},
    # Consumer Defensive
    "WMT": {"sector": "Consumer Defensive", "cap": 550e9},
    "PG": {"sector": "Consumer Defensive", "cap": 380e9},
    "KO": {"sector": "Consumer Defensive", "cap": 270e9},
    "COST": {"sector": "Consumer Defensive", "cap": 370e9},
    "PEP": {"sector": "Consumer Defensive", "cap": 230e9},
    "PM": {"sector": "Consumer Defensive", "cap": 150e9},
    # Energy
    "XOM": {"sector": "Energy", "cap": 480e9},
    "CVX": {"sector": "Energy", "cap": 290e9},
    "COP": {"sector": "Energy", "cap": 130e9},
    "SLB": {"sector": "Energy", "cap": 70e9},
    # Industrials
    "GE": {"sector": "Industrials", "cap": 180e9},
    "CAT": {"sector": "Industrials", "cap": 170e9},
    "UNP": {"sector": "Industrials", "cap": 150e9},
    "HON": {"sector": "Industrials", "cap": 130e9},
    "RTX": {"sector": "Industrials", "cap": 140e9},
    "LMT": {"sector": "Industrials", "cap": 110e9},
    "BA": {"sector": "Industrials", "cap": 120e9},
    "UPS": {"sector": "Industrials", "cap": 110e9},
    # Utilities
    "NEE": {"sector": "Utilities", "cap": 140e9},
    "DUK": {"sector": "Utilities", "cap": 80e9},
    "SO": {"sector": "Utilities", "cap": 80e9},
    # Materials
    "LIN": {"sector": "Materials", "cap": 90e9},
    "APD": {"sector": "Materials", "cap": 60e9}
}

@st.cache_data(ttl=30)
def get_live_price(symbol: str) -> float:
    symbol = symbol.strip().upper()
    if not symbol:
        return 0.0
    api_key = os.environ.get("FINNHUB_API_KEY")
    if api_key and not api_key.startswith("YOUR_"):
        try:
            url = "https://finnhub.io/api/v1/quote"
            res = requests.get(url, params={"symbol": symbol, "token": api_key}, timeout=5)
            if res.status_code == 200:
                data = res.json()
                if data.get("c", 0) > 0:
                    return float(data["c"])
        except Exception:
            pass
    try:
        t = yf.Ticker(symbol)
        df = t.history(period="1d")
        if not df.empty:
            return float(df["Close"].iloc[-1])
    except Exception:
        pass
    return 0.0

@st.cache_data(ttl=30)
def get_live_prices_batch(symbols: list) -> dict:
    if not symbols:
        return {}
    symbols = [s.strip().upper() for s in symbols]
    prices = {}
    api_key = os.environ.get("FINNHUB_API_KEY")
    if api_key and not api_key.startswith("YOUR_"):
        for sym in symbols:
            p = get_live_price(sym)
            if p > 0:
                prices[sym] = p
        if len(prices) == len(symbols):
            return prices

    try:
        data = yf.download(symbols, period="1d", group_by="ticker", progress=False)
        for sym in symbols:
            if sym not in prices:
                if len(symbols) == 1 and not data.empty:
                    prices[sym] = float(data["Close"].iloc[-1])
                elif sym in data and not data[sym].empty:
                    prices[sym] = float(data[sym]["Close"].dropna().iloc[-1])
        return prices
    except Exception:
        pass
    return {s: get_live_price(s) for s in symbols}

@st.cache_data(ttl=300)
def get_index_snapshots() -> list:
    symbols = ["^GSPC", "^DJI", "^IXIC", "^RUT", "^VIX", "GC=F", "CL=F"]
    names = {
        "^GSPC": "S&P 500", 
        "^DJI": "DOW 30", 
        "^IXIC": "NASDAQ", 
        "^RUT": "RUSSELL 2000",
        "^VIX": "VIX",
        "GC=F": "GOLD",
        "CL=F": "CRUDE OIL"
    }
    try:
        data = yf.download(symbols, period="30d", group_by="ticker", progress=False)
        records = []
        for sym in symbols:
            if sym in data:
                df = data[sym].dropna()
                if len(df) >= 2:
                    closes = df["Close"].tolist()
                    close_last = float(df["Close"].iloc[-1])
                    close_prev = float(df["Close"].iloc[-2])
                    pts_chg = close_last - close_prev
                    pct_chg = ((close_last - close_prev) / close_prev) * 100
                    records.append({
                        "name": names.get(sym, sym),
                        "close": close_last,
                        "pts": pts_chg,
                        "pct": pct_chg,
                        "series": closes
                    })
        return records
    except Exception:
        pass
    return []

@st.cache_data(ttl=600)
def get_market_heatmap_data() -> pd.DataFrame:
    tickers = list(HEATMAP_STOCKS.keys())
    try:
        data = yf.download(tickers, period="5d", group_by="ticker", progress=False)
        records = []
        for symbol in tickers:
            if symbol in data:
                df = data[symbol].dropna()
                if len(df) >= 2:
                    cl = float(df["Close"].iloc[-1])
                    cp = float(df["Close"].iloc[-2])
                    chg = ((cl - cp) / cp) * 100
                    records.append({
                        "ticker": symbol,
                        "sector": HEATMAP_STOCKS[symbol]["sector"],
                        "cap": HEATMAP_STOCKS[symbol]["cap"],
                        "change": chg
                    })
        return pd.DataFrame(records)
    except Exception:
        pass
    return pd.DataFrame()

@st.cache_data(ttl=600)
def get_sector_performance() -> list:
    etfs = ["XLK", "XLF", "XLV", "XLY", "XLE", "XLU"]
    names = {"XLK": "Technology", "XLF": "Financials", "XLV": "Healthcare", "XLY": "Consumer Disc.", "XLE": "Energy", "XLU": "Utilities"}
    try:
        data = yf.download(etfs, period="1mo", group_by="ticker", progress=False)
        records = []
        for sym in etfs:
            if sym in data:
                df = data[sym].dropna()
                if len(df) >= 2:
                    cl = float(df["Close"].iloc[-1])
                    cp_1 = float(df["Close"].iloc[-2])
                    change_1d = ((cl - cp_1) / cp_1) * 100
                    cp_5 = float(df["Close"].iloc[-5]) if len(df) >= 5 else cp_1
                    change_5d = ((cl - cp_5) / cp_5) * 100
                    momentum = "UP" if change_1d > 0 and change_5d > 0 else ("DOWN" if change_1d < 0 and change_5d < 0 else "MIXED")
                    records.append({"name": names.get(sym, sym), "ticker": sym, "close": cl, "change": change_1d, "momentum": momentum})
        records.sort(key=lambda x: x["change"], reverse=True)
        return records
    except Exception:
        pass
    return []

@st.cache_data(ttl=600)
def get_market_breadth_index() -> dict:
    core = list(HEATMAP_STOCKS.keys())
    try:
        data = yf.download(core, period="80d", group_by="ticker", progress=False)
        a20 = a60 = tv = 0
        for tk in core:
            if tk in data:
                df = data[tk].dropna()
                if len(df) >= 60:
                    cl = float(df["Close"].iloc[-1])
                    s20 = float(df["Close"].rolling(20).mean().iloc[-1])
                    s60 = float(df["Close"].rolling(60).mean().iloc[-1])
                    if cl > s20: a20 += 1
                    if cl > s60: a60 += 1
                    tv += 1
        if tv > 0:
            return {"pct_20": (a20 / tv) * 100, "pct_60": (a60 / tv) * 100, "valid": True}
    except Exception:
        pass
    return {"pct_20": 50.0, "pct_60": 50.0, "valid": False}

@st.cache_data(ttl=600)
def get_market_scanners() -> dict:
    """Rank the tracked universe by change, volume and window extremes.

    Delegates to marketdata.fetch_scanner_universe. The version this replaces
    discarded every real record and rebuilt the entire table from
    `sum(ord(c) for c in ticker)` whenever fewer than five symbols resolved —
    producing a complete, plausible, entirely fictional set of market movers
    that the UI rendered exactly like live data.

    Partial coverage is now reported instead of topped up, and the extremes are
    labelled by the window actually measured rather than as "52-week".
    """
    try:
        result = marketdata.fetch_scanner_universe(
            list(HEATMAP_STOCKS.keys()), lookback_days=65)
    except marketdata.DataUnavailable as exc:
        return {
            "ok": False, "error": str(exc), "coverage": 0.0,
            "requested": len(HEATMAP_STOCKS), "resolved": 0, "window_days": 65,
            "gainers": [], "losers": [], "trending": [],
            "unusual_vol": [], "new_hi": [], "new_lo": [],
        }

    at_high = [r for r in result.records if r["at_window_high"]]
    at_low = [r for r in result.records if r["at_window_low"]]

    return {
        "ok": True,
        "error": None,
        "coverage": result.coverage,
        "requested": result.requested,
        "resolved": result.resolved,
        "window_days": result.window_days,
        "gainers": result.top("change", 8),
        "losers": result.top("change", 8, ascending=True),
        # vol_ratio is None when the average volume was zero, so sort those last
        # rather than letting None compare against floats.
        "trending": sorted(
            [r for r in result.records if r.get("vol_ratio") is not None],
            key=lambda r: r["vol_ratio"], reverse=True)[:8],
        "unusual_vol": result.top("volume", 8),
        # Genuinely at the window extreme, not "the top movers if none qualify".
        "new_hi": sorted(at_high, key=lambda r: r["change"], reverse=True)[:8],
        "new_lo": sorted(at_low, key=lambda r: r["change"])[:8],
    }


@st.cache_data(ttl=300)
def get_futures_commodities() -> list:
    symbols = [
        "ES=F", "NQ=F", "YM=F", "RTY=F",
        "GC=F", "CL=F", "SI=F", "NG=F", "HG=F", "ZC=F", "ZW=F",
        "^TNX", "^VIX", "^IRX",
        "BTC-USD", "ETH-USD", "SOL-USD",
        "EURUSD=X", "JPY=X"
    ]
    names = {
        "ES=F": "S&P 500 Futures",
        "NQ=F": "Nasdaq Futures",
        "YM=F": "Dow Futures",
        "RTY=F": "Russell 2000 Futures",
        "GC=F": "Gold Futures",
        "CL=F": "Crude Oil WTI",
        "SI=F": "Silver Futures",
        "NG=F": "Natural Gas",
        "HG=F": "Copper Futures",
        "ZC=F": "Corn Futures",
        "ZW=F": "Wheat Futures",
        "^TNX": "10-Yr Treasury Yield",
        "^VIX": "VIX Volatility Index",
        "^IRX": "13-Wk Treasury Bill",
        "BTC-USD": "Bitcoin (BTC)",
        "ETH-USD": "Ethereum (ETH)",
        "SOL-USD": "Solana (SOL)",
        "EURUSD=X": "EUR / USD",
        "JPY=X": "USD / JPY"
    }
    records = []
    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            df = t.history(period="5d")
            if len(df) >= 2:
                cl = float(df["Close"].iloc[-1])
                cp = float(df["Close"].iloc[-2])
                chg = cl - cp
                chg_pct = (chg / cp) * 100
                records.append({
                    "symbol": sym,
                    "name": names.get(sym, sym),
                    "price": cl,
                    "change": chg,
                    "pct": chg_pct
                })
        except Exception:
            pass
    if len(records) >= 5:
        return records

    return [
        {"symbol": "ES=F", "name": "S&P 500 Futures", "price": 5420.25, "change": 12.50, "pct": 0.23},
        {"symbol": "NQ=F", "name": "Nasdaq Futures", "price": 19250.75, "change": 88.20, "pct": 0.46},
        {"symbol": "YM=F", "name": "Dow Futures", "price": 39510.00, "change": -45.00, "pct": -0.11},
        {"symbol": "RTY=F", "name": "Russell 2000 Futures", "price": 2045.30, "change": 14.20, "pct": 0.70},
        {"symbol": "GC=F", "name": "Gold Futures", "price": 2354.20, "change": 14.80, "pct": 0.63},
        {"symbol": "CL=F", "name": "Crude Oil WTI", "price": 81.35, "change": -0.42, "pct": -0.51},
        {"symbol": "SI=F", "name": "Silver Futures", "price": 30.25, "change": 0.18, "pct": 0.60},
        {"symbol": "NG=F", "name": "Natural Gas", "price": 2.65, "change": 0.04, "pct": 1.53},
        {"symbol": "HG=F", "name": "Copper Futures", "price": 4.45, "change": -0.03, "pct": -0.67},
        {"symbol": "^TNX", "name": "10-Yr Treasury Yield", "price": 4.225, "change": 0.015, "pct": 0.36},
        {"symbol": "^VIX", "name": "VIX Volatility Index", "price": 14.85, "change": -0.35, "pct": -2.30},
        {"symbol": "BTC-USD", "name": "Bitcoin (BTC)", "price": 64500.00, "change": 1250.00, "pct": 1.98},
        {"symbol": "ETH-USD", "name": "Ethereum (ETH)", "price": 3480.00, "change": 65.00, "pct": 1.90},
        {"symbol": "SOL-USD", "name": "Solana (SOL)", "price": 142.50, "change": 4.20, "pct": 3.04},
        {"symbol": "EURUSD=X", "name": "EUR / USD", "price": 1.0885, "change": 0.0012, "pct": 0.11},
        {"symbol": "JPY=X", "name": "USD / JPY", "price": 157.20, "change": -0.45, "pct": -0.29}
    ]


def get_recent_insiders() -> list:
    """Recent insider transactions. Returns [] until a real source is wired up.

    This function previously returned ten hardcoded transactions attributed to
    real, named executives — "Cook Timothy D", "Nadella Satya", "Musk Elon" —
    with invented prices, share counts and dates stamped relative to
    datetime.now() so they always looked fresh. It made no network call at all.

    That is the most serious fabrication in the codebase: invented securities
    dealings attributed to identifiable real people, rendered indistinguishably
    from filed data. Deleted outright rather than relabelled.

    A real implementation needs SEC Form 4 filings (EDGAR full-text search, or
    a vendor feed). Until then the panel shows an empty state that says so.
    """
    return []

@st.cache_data(ttl=600)
def get_macro_news() -> list:
    try:
        t = yf.Ticker("^GSPC")
        news_data = t.news or []
        parsed = []
        for article in news_data[:8]:
            content = article.get("content") or {}
            if content:
                title = content.get("title") or ""
                summary = content.get("summary") or ""
                prov = content.get("provider") or {}
                publisher = prov.get("displayName") or "Feed"
                link = content.get("clickThroughUrl", {}).get("url") or content.get("canonicalUrl", {}).get("url") or ""
                pds = content.get("pubDate") or ""
                dt = datetime.now()
                if pds:
                    try:
                        if pds.endswith('Z'): pds = pds[:-1]
                        dt = datetime.fromisoformat(pds)
                    except Exception:
                        pass
                words = (title + " " + summary).lower().replace(",", " ").split()
                pw = {'growth', 'recovery', 'gain', 'surges', 'rally', 'beat', 'bullish', 'expansion', 'optimism', 'boost'}
                nw = {'inflation', 'recession', 'rate hike', 'cut', 'slump', 'down', 'bearish', 'fear', 'miss', 'slashes'}
                p = sum(1 for w in words if w in pw)
                n = sum(1 for w in words if w in nw)
                sc = (p - n) / (p + n + 1)
                if sc > 0.05:
                    badge, bcls = "BULLISH", "sent-bullish"
                elif sc < -0.05:
                    badge, bcls = "BEARISH", "sent-bearish"
                else:
                    badge, bcls = "NEUTRAL", "sent-neutral"
                parsed.append({"title": title, "publisher": publisher, "link": link, "time": dt, "badge": badge, "class": bcls})
        return parsed
    except Exception:
        pass
    return []

@st.cache_data(ttl=600)
def get_ticker_info(symbol: str) -> dict:
    """Quote and fundamentals, or an all-None record marked ok=False.

    Delegates to marketdata.fetch_ticker_info. The version this replaces
    invented a complete company on failure — market cap 250e9, P/E 24.5, EPS
    4.5, beta 1.1, a 52-week range of 120-180 — and derived the day's change
    percentage from `sum(ord(c) for c in symbol)`, the arithmetic of the
    ticker's letters. None of that was distinguishable from real data once it
    reached the screen.

    Individual fields the provider omits stay None rather than becoming 0.0,
    so an unknown P/E renders as "unavailable" instead of a real P/E of zero.
    """
    try:
        payload = marketdata.fetch_ticker_info(symbol)
    except marketdata.DataUnavailable as exc:
        blank = {k: None for k in (
            "previous_close", "open", "bid", "ask", "volume", "avg_volume",
            "market_cap", "beta", "pe_ratio", "eps", "day_low", "day_high",
            "fifty_two_low", "fifty_two_high", "day_change_pct", "sector")}
        blank.update({"ok": False, "symbol": symbol.strip().upper(),
                      "long_name": symbol.strip().upper(), "error": str(exc)})
        return blank

    record = payload.to_dict()
    record["ok"] = True
    record["error"] = None
    record["long_name"] = record.get("long_name") or record["symbol"]
    return record


def fmt_money(value, digits: int = 2, dash: str = "\u2014") -> str:
    """Currency, or an em dash when the figure was never measured."""
    return dash if value is None else f"${value:,.{digits}f}"


def fmt_pct(value, digits: int = 2, dash: str = "\u2014", signed: bool = True) -> str:
    if value is None:
        return dash
    sign = "+" if (signed and value >= 0) else ""
    return f"{sign}{value:.{digits}f}%"


def fmt_num(value, digits: int = 2, dash: str = "\u2014") -> str:
    return dash if value is None else f"{value:,.{digits}f}"


def fmt_cap(value, dash: str = "\u2014") -> str:
    """Market cap in compact magnitudes."""
    if value is None:
        return dash
    for cutoff, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(value) >= cutoff:
            return f"${value / cutoff:,.2f}{suffix}"
    return f"${value:,.0f}"


def value_class(value) -> str:
    """CSS class for a signed figure, neutral when it was not measured."""
    if value is None:
        return "rv-muted"
    return "rv-pos" if value >= 0 else "rv-neg"


@st.cache_data(ttl=600)
def get_rss_news(symbol: str) -> list:
    """Fetch news headlines from Yahoo Finance RSS feed and Firecrawl live scraper."""
    symbol = symbol.strip().upper()
    parsed = []
    seen_titles = set()
    
    # Source 1: Firecrawl Live Web Scraper (if active)
    fc_key = os.environ.get("FIRECRAWL_API_KEY")
    if fc_key and fc_key.strip() and not fc_key.startswith("YOUR_"):
        try:
            from data_fetcher import fetch_firecrawl_news
            fc_news = fetch_firecrawl_news(symbol if symbol != "^GSPC" else "stock market", fc_key.strip())
            for fn in fc_news:
                t = fn.get("headline", "")
                if not t or t.lower() in seen_titles: continue
                seen_titles.add(t.lower())
                parsed.append({
                    "title": t,
                    "link": fn.get("url", ""),
                    "pub_date": "Live Firecrawl",
                    "date": "Live Firecrawl",
                    "source": fn.get("source", "Firecrawl Wire"),
                    "summary_snippet": fn.get("summary", "")[:250],
                    "sentiment_score": 0.25,
                    "badge": "BULLISH",
                    "class": "sent-bullish"
                })
        except Exception:
            pass

    # Source 2: Yahoo Finance RSS feed
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            xml_data = resp.read()
        root = ET.fromstring(xml_data)
        items = root.findall(".//item")
        
        pos_phrases = ["beating expectations", "surpassing guidance", "strategic breakthrough", "increased allocation", "upgrade", "growth acceleration", "support holds"]
        neg_phrases = ["regulatory probe", "supply constraints", "device costs rising", "revenue miss", "guidance cut", "downgrade", "resistance ceiling holds"]
        
        for item in items[:10]:
            title = (item.findtext("title") or "").strip()
            if not title or title.lower() in seen_titles:
                continue
            seen_titles.add(title.lower())

            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            source = (item.findtext("source") or "Yahoo Finance").strip()
            summary_snippet = (item.findtext("description") or "").strip()
            
            combined_text = (title + " " + summary_snippet).lower()
            pos_count = sum(1 for phrase in pos_phrases if phrase in combined_text)
            neg_count = sum(1 for phrase in neg_phrases if phrase in combined_text)
            
            total_detected = pos_count + neg_count
            sa = (pos_count - neg_count) / (total_detected + 1)
            
            if sa > 0:
                badge, bcls = "BULLISH", "sent-bullish"
            elif sa < 0:
                badge, bcls = "BEARISH", "sent-bearish"
            else:
                badge, bcls = "NEUTRAL", "sent-neutral"
                
            parsed.append({
                "title": title,
                "link": link,
                "pub_date": pub_date,
                "date": pub_date,
                "source": source,
                "summary_snippet": summary_snippet,
                "sentiment_score": sa,
                "badge": badge,
                "class": bcls
            })
        return parsed
    except Exception:
        pass
    return parsed


import base64

def get_image_base64(path):
    try:
        import os
        if os.path.exists(path):
            with open(path, "rb") as image_file:
                encoded = base64.b64encode(image_file.read()).decode()
                return f"data:image/png;base64,{encoded}"
    except Exception:
        pass
    
    # Premium, high-resolution Unsplash financial stock graphics fallbacks
    fallbacks = [
        "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?w=600&auto=format&fit=crop&q=80",  # Dark aesthetic candlestick chart
        "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=600&auto=format&fit=crop&q=80",  # Tech green indicator screen
        "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600&auto=format&fit=crop&q=80"   # Corporate skyscraper skyscraper finance
    ]
    if "news_chart" in path:
        return fallbacks[0]
    elif "news_tech" in path:
        return fallbacks[1]
    else:
        return fallbacks[2]

def clean_html(s: str) -> str:
    return "".join(line.strip() for line in s.split("\n"))

def render_rich_news_card(n, idx) -> str:
    from urllib.parse import urlparse
    dom = urlparse(n.get('link', '')).netloc or "finance.yahoo.com"
    img_paths = ["assets/news_chart.png", "assets/news_tech.png", "assets/news_corp.png"]
    img_path = img_paths[idx % 3]
    img_b64 = get_image_base64(img_path)
    
    # Clean source name to remove Firecrawl / API mentions
    raw_src = str(n.get('source', '') or 'Market Wire').strip()
    if any(k in raw_src.lower() for k in ['firecrawl', 'rss', 'api', 'scraper', 'yahoo']):
        src_label = "MARKET WIRE"
    else:
        src_label = raw_src.upper()

    # Clean date tag
    raw_date = str(n.get('pub_date', '') or n.get('date', '')).strip()
    if 'firecrawl' in raw_date.lower():
        date_label = "Live Wire"
    else:
        date_label = raw_date
    
    # Split description into nice bullets/sentences for structured captions
    desc = n.get('summary_snippet', '') or ''
    sentences = [s.strip() for s in desc.split('.') if s.strip()]
    bullet_list = ""
    for s in sentences[:3]:
        bullet_list += f"<li style='margin-bottom: 4px; font-size: 13px; color: var(--rv-text-muted); line-height: 1.4; font-family: \"Inter\", sans-serif;'>{s}.</li>"
    if not bullet_list:
        bullet_list = f"<li style='margin-bottom: 4px; font-size: 13px; color: var(--rv-text-muted); font-family: \"Inter\", sans-serif;'>Latest market catalyst details.</li>"
        
    badge_html = f"""<span class="{n.get('class', 'sent-neutral')}" style="margin-left: auto; font-size: 10px; font-weight: 700; border-radius: 3px; padding: 1px 6px; background: rgba(138,148,166,0.1); border: 1px solid currentColor;">{n.get('badge', 'NEUTRAL')}</span>"""
    
    header_html = f"""
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap;">
        <img src="https://www.google.com/s2/favicons?sz=64&domain={dom}" style="width: 18px; height: 18px; border-radius: 3px;" />
        <span style="font-size: 11px; font-weight: 700; color: var(--rv-text); text-transform: uppercase; font-family: 'JetBrains Mono', monospace;">{n.get('source', 'NEWS')}</span>
        <span style="font-size: 11px; color: var(--rv-text-muted);">&middot; {n.get('pub_date', '')}</span>
        {badge_html}
    </div>
    """

    
    title_html = f"""
    <div style="margin-bottom: 10px;">
        <a href="{n.get('link', '#')}" target="_blank" style="font-size: 16px; font-weight: 700; color: var(--rv-info); text-decoration: none; font-family: 'Inter', sans-serif; line-height: 1.3; transition: color 0.15s ease-in-out;" 
           onmouseover="this.style.color='var(--rv-pos)'" onmouseout="this.style.color='var(--rv-info)'">
            {n.get('title', 'Market Update Headline')}
        </a>
    </div>
    """
    
    content_html = f"""
    <ul style="margin: 0; padding-left: 14px; list-style-type: square;">
        {bullet_list}
    </ul>
    """

    if idx % 2 == 0:
        # Layout 1: Top large hero banner style card (full width image!)
        card_html = f"""
        <div style="background-color: var(--rv-surface); border: 1px solid var(--rv-border); border-radius: 8px; margin-bottom: 16px; display: flex; flex-direction: column; overflow: hidden; transition: border-color 0.2s ease-in-out;">
            <img src="{img_b64}" style="width: 100%; height: 210px; object-fit: cover; border-bottom: 1px solid var(--rv-border);" />
            <div style="padding: 16px;">
                {header_html}
                {title_html}
                {content_html}
            </div>
        </div>
        """
    else:
        # Layout 2: Tall side-banner style card (image dominates on the left)
        card_html = f"""
        <div style="background-color: var(--rv-surface); border: 1px solid var(--rv-border); border-radius: 8px; padding: 16px; margin-bottom: 16px; display: flex; gap: 16px; align-items: stretch; transition: border-color 0.2s ease-in-out;">
            <img src="{img_b64}" style="width: 220px; height: 150px; border-radius: 4px; object-fit: cover; border: 1px solid var(--rv-border); flex-shrink: 0;" />
            <div style="flex-grow: 1; min-width: 0; display: flex; flex-direction: column; justify-content: center;">
                {header_html}
                {title_html}
                {content_html}
            </div>
        </div>
        """
    return card_html

def calculate_rsi(close_prices: pd.Series, period: int = 14) -> float:
    P = close_prices.tolist() if isinstance(close_prices, pd.Series) else list(close_prices)
    if len(P) < period + 1:
        return 50.0
    gains = []
    losses = []
    for idx in range(1, len(P)):
        diff = P[idx] - P[idx-1]
        if diff > 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(-diff)
            
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    for idx in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[idx]) / period
        avg_loss = (avg_loss * (period - 1) + losses[idx]) / period
        
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))

def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def calculate_macd(series: pd.Series) -> tuple:
    if len(series) < 26:
        return 0.0, 0.0, 0.0
    ema12 = calculate_ema(series, 12)
    ema26 = calculate_ema(series, 26)
    macd_line = ema12 - ema26
    signal_line = calculate_ema(macd_line, 9)
    histogram = macd_line - signal_line
    return float(macd_line.iloc[-1]), float(signal_line.iloc[-1]), float(histogram.iloc[-1])

def detect_patterns(df: pd.DataFrame) -> list:
    if df.empty or len(df) < 3:
        return []
    lr = df.iloc[-1]
    pr = df.iloc[-2]
    oc, hc, lc, cc = float(lr["Open"]), float(lr["High"]), float(lr["Low"]), float(lr["Close"])
    op, cp = float(pr["Open"]), float(pr["Close"])
    rng = hc - lc
    body = abs(oc - cc)
    det = []
    if rng > 0 and (body / rng) < 0.08:
        det.append("Doji")
    lw = min(oc, cc) - lc
    uw = hc - max(oc, cc)
    if body > 0 and rng > 0:
        if lw > 2 * body and body < 0.3 * rng and uw < 0.2 * rng:
            det.append("Hammer")
    if body > 0 and rng > 0:
        if uw > 2 * body and body < 0.3 * rng and lw < 0.2 * rng:
            det.append("Shooting Star")
    if cp < op and cc > oc:
        if oc <= cp and cc >= op:
            det.append("Bullish Engulfing")
    elif cp > op and cc < oc:
        if oc >= cp and cc <= op:
            det.append("Bearish Engulfing")
    if len(df) >= 20:
        highs_20 = df["High"].tail(20)
        lows_20 = df["Low"].tail(20)
        peak_val = float(highs_20.max())
        trough_val = float(lows_20.min())
        near_peaks = highs_20[highs_20 >= peak_val * 0.99]
        if len(near_peaks) >= 2:
            first_peak = near_peaks.index[0]
            last_peak = near_peaks.index[-1]
            if first_peak != last_peak:
                det.append("Double Top")
        near_troughs = lows_20[lows_20 <= trough_val * 1.01]
        if len(near_troughs) >= 2:
            first_trough = near_troughs.index[0]
            last_trough = near_troughs.index[-1]
            if first_trough != last_trough:
                det.append("Double Bottom")
    return det

def classify_channel(df: pd.DataFrame) -> str:
    if len(df) < 60:
        return "Insufficient Data"
    sma20 = df["Close"].rolling(20).mean()
    sma60 = df["Close"].rolling(60).mean()
    s20_now = float(sma20.iloc[-1])
    s20_prev = float(sma20.iloc[-10]) if len(sma20) >= 10 else s20_now
    s60_now = float(sma60.iloc[-1])
    s60_prev = float(sma60.iloc[-10]) if len(sma60) >= 10 else s60_now
    slope_20 = (s20_now - s20_prev) / (s20_prev + 1e-9)
    slope_60 = (s60_now - s60_prev) / (s60_prev + 1e-9)
    if slope_20 > 0.005 and slope_60 > 0.005:
        return "Ascending Channel"
    elif slope_20 < -0.005 and slope_60 < -0.005:
        return "Descending Channel"
    elif abs(slope_20) < 0.005 and abs(slope_60) < 0.005:
        return "Consolidation"
    elif slope_20 > 0.01 and slope_60 < 0:
        return "Wedge Breakout"
    else:
        return "Mixed Trend"

def process_advanced_analytics(symbol: str, res: dict) -> dict:
    """Technical analytics for the Research tab.

    Returns ``ok=False`` with every numeric field None when the input has too
    little history, rather than a plausible neutral reading.
    """
    df = res.get("prices", pd.DataFrame())
    if df.empty or "Close" not in df.columns or len(df) < 5:
        # Not enough history to compute anything. The version this replaces
        # returned a complete, confident analysis here: RSI exactly 50, a quant
        # score of exactly 50, support and resistance derived from a $150.00
        # placeholder price, and a position-sizing paragraph quoting "15.0%
        # annualized volatility" and a "10.0%" capital cap — none of it
        # measured, all of it rendered identically to a real reading.
        #
        # Every field is None now, and the UI renders None as unavailable.
        return {
            "ok": False,
            "reason": "not enough price history to compute indicators",
            "rsi": None, "support": None, "resistance": None,
            "crossover_status": None, "action_label": None,
            "action_class": "badge-hold", "ratio_20": None, "ratio_60": None,
            "quant_score": None, "position_advice": None, "channel": None,
            "sma_200": None, "macd": None, "macd_signal": None, "macd_hist": None,
            "ema_9": None, "ema_20": None, "volatility": None, "s_total": None,
            "sma_20": None, "sma_60": None,
        }
    
    close_series = df["Close"].dropna()
    P = close_series.tolist()
    if not P:
        # Guarded by the length check above, but never substitute a price.
        return {"ok": False, "reason": "price series is empty",
                **{k: None for k in (
                    "rsi", "support", "resistance", "crossover_status",
                    "action_label", "ratio_20", "ratio_60", "quant_score",
                    "position_advice", "channel", "sma_200", "macd",
                    "macd_signal", "macd_hist", "ema_9", "ema_20",
                    "volatility", "s_total", "sma_20", "sma_60")},
                "action_class": "badge-hold"}
    price = P[-1]
    
    # 20 SMA & 60 SMA with safe slicing
    sub20 = P[-20:]
    sma20_val = sum(sub20) / len(sub20)
    sub60 = P[-60:]
    sma60_val = sum(sub60) / len(sub60)
    sub200 = P[-200:]
    sma200_val = sum(sub200) / len(sub200)
    
    # RSI
    rsi_raw = calculate_rsi(close_series, 14)
    rsi_val = float(rsi_raw) if not np.isnan(rsi_raw) else 50.0
    
    # Annualized Volatility
    if len(P) >= 2:
        log_returns = [np.log(P[i] / P[i-1]) for i in range(1, len(P)) if P[i-1] > 0 and P[i] > 0]
        sigma = np.std(log_returns, ddof=1) if len(log_returns) > 1 else 0.0
        volatility = float(sigma * np.sqrt(252) * 100)
        if np.isnan(volatility):
            volatility = 15.0
    else:
        volatility = 15.0
        
    # S_total from general rss news
    rss_news = get_rss_news(symbol)
    s_total = 0.0
    if rss_news:
        scores = [n["sentiment_score"] for n in rss_news if "sentiment_score" in n]
        if scores:
            s_total = sum(scores) / len(scores)
        
    # Support and resistance
    low_min = float(df["Low"].dropna().tail(20).min()) if "Low" in df.columns and not df["Low"].dropna().empty else price * 0.95
    high_max = float(df["High"].dropna().tail(20).max()) if "High" in df.columns and not df["High"].dropna().empty else price * 1.05
    support_floor = low_min if not np.isnan(low_min) else price * 0.95
    resistance_ceiling = high_max if not np.isnan(high_max) else price * 1.05
    
    # Decision Logic
    is_strong_buy = (price > sma20_val and sma20_val > sma60_val and rsi_val < 65) or (s_total >= 0.25 and price > sma20_val and rsi_val < 65)
    is_sell = (price < sma20_val and sma20_val < sma60_val and rsi_val > 35) or (s_total <= -0.25 and price < sma20_val and rsi_val > 35)
    
    if is_strong_buy:
        action, aclass = "STRONG BUY", "badge-strong-buy"
    elif is_sell:
        action, aclass = "REDUCE EXPOSURE / SELL", "badge-sell"
    else:
        action, aclass = "HOLD", "badge-hold"
        
    ratio_20 = price / (sma20_val + 1e-9)
    ratio_60 = price / (sma60_val + 1e-9)
    
    if sma20_val > sma60_val:
        crossover_status = "Bullish SMA Alignment (SMA20 > SMA60)"
    else:
        crossover_status = "Bearish SMA Alignment (SMA20 < SMA60)"
        
    macd_val, macd_sig, macd_hist = calculate_macd(close_series)
    ema9_val = float(calculate_ema(close_series, 9).iloc[-1]) if len(close_series) >= 9 else price
    ema20_val = float(calculate_ema(close_series, 20).iloc[-1]) if len(close_series) >= 20 else price
    channel = classify_channel(df)
    
    vol_cap = min(25.0, (10.0 / (volatility + 1e-9)) * 100) if volatility > 0 else 10.0
    advice = f"Risk Protocol Status: Current asset exhibits a calculated 60-day annualized volatility metric of {volatility:.1f}%. The position-sizing engine advises capping your theoretical capital deployment to exactly {vol_cap:.1f}% of total available portfolio equity balance sheets to shield capital from sudden price flips."
    
    return {
        "rsi": rsi_val, "support": support_floor, "resistance": resistance_ceiling,
        "crossover_status": crossover_status, "action_label": action,
        "action_class": aclass, "ratio_20": ratio_20, "ratio_60": ratio_60,
        "quant_score": (75.0 if is_strong_buy else (30.0 if is_sell else 50.0)),
        "position_advice": advice,
        "channel": channel,
        "sma_200": sma200_val, "macd": macd_val, "macd_signal": macd_sig, "macd_hist": macd_hist,
        "ema_9": ema9_val, "ema_20": ema20_val,
        "volatility": volatility,
        "s_total": s_total,
        "sma_20": sma20_val,
        "sma_60": sma60_val
    }

def make_sparkline(series, positive=None, color=None):
    """Small inline trend line.

    Takes a direction rather than a colour: Plotly rasterises server-side and
    cannot resolve CSS custom properties, so passing "var(--rv-pos)" here
    silently produced an uncoloured trace. Both the stroke and its fill are
    derived from the active theme instead.
    """
    if color is None:
        color = T.pos if positive else (T.neg if positive is not None else T.info)
    fillcolor = rgba(color, 0.08)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=series,
        mode='lines',
        line=dict(color=color, width=1.8),
        fill='tozeroy',
        fillcolor=fillcolor,
        hoverinfo='none', 
        showlegend=False
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(t=2, b=2, l=2, r=2), height=35,
        xaxis=dict(visible=False, showgrid=False, zeroline=False),
        yaxis=dict(visible=False, showgrid=False, zeroline=False)
    )
    return fig

def make_ml_prediction_chart(forecast_data: list, current_price: float, symbol: str):
    df_fc = pd.DataFrame(forecast_data)
    fig = go.Figure()

    if not df_fc.empty and "date" in df_fc.columns and "predicted_close" in df_fc.columns:
        dates = df_fc["date"]
        preds = df_fc["predicted_close"]
        upper = df_fc.get("upper_bound", preds * 1.05)
        lower = df_fc.get("lower_bound", preds * 0.95)

        # 95% Confidence interval shaded region
        fig.add_trace(go.Scatter(
            x=list(dates) + list(dates)[::-1],
            y=list(upper) + list(lower)[::-1],
            fill='toself',
            fillcolor='rgba(88, 166, 255, 0.12)',
            line=dict(color='rgba(255,255,255,0)'),
            hoverinfo="none",
            name="95% Confidence Interval"
        ))

        # Predicted Close Trajectory
        fig.add_trace(go.Scatter(
            x=dates,
            y=preds,
            mode='lines+markers',
            name='ML Predicted Price',
            line=dict(color='#00E676', width=2.5),
            marker=dict(size=4, color='#00E676')
        ))

    fig.update_layout(
        title=dict(text=f"30-Day Predictive Trajectory Forecast ({symbol})", font=dict(size=13, color='#FFFFFF', family='Inter')),
        template="plotly_dark",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=320,
        margin=dict(l=10, r=10, t=35, b=10),
        xaxis=dict(showgrid=True, gridcolor='#1E2433', tickfont=dict(size=10, color='#8A94A6')),
        yaxis=dict(showgrid=True, gridcolor='#1E2433', tickfont=dict(size=10, color='#8A94A6'), tickprefix="$"),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10, color='#8A94A6'))
    )
    return fig


def make_feature_importance_chart(feature_importances: list):
    df_feat = pd.DataFrame(feature_importances)
    fig = go.Figure()

    if not df_feat.empty and "feature" in df_feat.columns and "importance" in df_feat.columns:
        df_sorted = df_feat.sort_values("importance", ascending=True)
        fig.add_trace(go.Bar(
            x=df_sorted["importance"],
            y=df_sorted["feature"],
            orientation='h',
            marker=dict(
                color=df_sorted["importance"],
                colorscale=[[0, '#1E2433'], [1, '#00E676']],
                line=dict(color='#2A3142', width=1)
            ),
            hovertemplate="Feature: %{y}<br>Weight: %{x:.1f}%<extra></extra>"
        ))

    fig.update_layout(
        title=dict(text="Top Machine Learning Predictor Features", font=dict(size=13, color='#FFFFFF', family='Inter')),
        template="plotly_dark",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=320,
        margin=dict(l=10, r=10, t=35, b=10),
        xaxis=dict(title="Feature Importance (%)", showgrid=True, gridcolor='#1E2433', tickfont=dict(size=10, color='#8A94A6')),
        yaxis=dict(showgrid=False, tickfont=dict(size=10, color='#C9D1D9')),
        showlegend=False
    )
    return fig


def format_volume(vol):

    if vol >= 1e6:
        return f"{vol/1e6:.1f}M"
    elif vol >= 1e3:
        return f"{vol/1e3:.0f}K"
    return f"{vol:.0f}"

def format_market_cap(val):
    if val >= 1e12:
        return f"${val/1e12:.2f}T"
    elif val >= 1e9:
        return f"${val/1e9:.2f}B"
    elif val >= 1e6:
        return f"${val/1e6:.2f}M"
    return f"${val:.0f}"

def render_scanner(rows, signal, key=None, height=None):
    """A scanner panel: one themed row per symbol, click to research it.

    Two defects in the original are fixed here.

    Layout: the five columns had fixed pixel widths summing to 330px inside a
    third-width column that is roughly 205px, so the cells shrank and their
    contents collided into an unreadable run ("AMD$514.39+6.50%24.9M"). This is
    a grid whose columns are fractional with a minimum, so they compress
    proportionally and truncate instead of overlapping.

    Navigation: ticker cells were anchors to /?tab=RESEARCH&ticker=X, which
    reloaded the whole Streamlit session on every click. They are now plain
    elements carrying data-rv-ticker, which the chrome component's delegated
    click handler turns into an in-place rerun.

    st.dataframe would also solve both and add sorting, but it renders through
    glide-data-grid, which takes its colours from Streamlit's build-time config
    rather than CSS - so it stays dark under a light palette and cannot follow
    the theme. Themed markup wins here.
    """
    if not rows:
        st.html(fx.empty_state("No matches", "◇"))
        return

    body = []
    for r in rows:
        change = r["change"]
        cls = "rv-pos" if change >= 0 else "rv-neg"
        sign = "+" if change >= 0 else ""
        row_signal = r.get("signal", signal)
        pill = {
            "GAINER": "pill-pos", "52W HIGH": "pill-pos",
            "LOSER": "pill-neg", "52W LOW": "pill-neg",
        }.get(row_signal, "pill-neut")
        body.append(
            f'<div class="rv-scan-row" data-rv-ticker="{r["ticker"]}" '
            f'role="button" tabindex="0" title="Research {r["ticker"]}">'
            f'<span class="rv-scan-sym">{r["ticker"]}</span>'
            f'<span class="rv-num rv-right">${r["close"]:,.2f}</span>'
            f'<span class="rv-num rv-right {cls}">{sign}{change:.2f}%</span>'
            f'<span class="rv-num rv-right rv-muted">{format_volume(r["volume"])}</span>'
            f'<span class="rv-right"><span class="{pill}">{row_signal}</span></span>'
            f"</div>"
        )

    st.html(
        '<div class="rv-card rv-card--flush rv-scan">'
        '<div class="rv-scan-row rv-scan-head">'
        '<span>Ticker</span><span class="rv-right">Price</span>'
        '<span class="rv-right">Chg</span><span class="rv-right">Vol</span>'
        '<span class="rv-right">Signal</span></div>'
        + "".join(body) + "</div>"
    )

def make_heatmap_chart(df: pd.DataFrame):
    if df.empty:
        return go.Figure()
    labels, parents, values, color_vals, custom_data = [], [], [], [], []
    
    # Root
    labels.append("Market")
    parents.append("")
    values.append(df["cap"].sum())
    color_vals.append(0.0)
    custom_data.append("")
    
    # Sectors
    sectors = df["sector"].unique()
    for sec in sectors:
        sec_df = df[df["sector"] == sec]
        labels.append(sec)
        parents.append("Market")
        values.append(sec_df["cap"].sum())
        sec_chg = sec_df["change"].mean()
        color_vals.append(sec_chg)
        custom_data.append(f"{sec_chg:+.2f}%")
        
    # Tickers
    for _, row in df.iterrows():
        labels.append(row["ticker"])
        parents.append(row["sector"])
        values.append(row["cap"])
        color_vals.append(row["change"])
        custom_data.append(f"{row['change']:+.2f}%")
        
    fig = go.Figure(go.Treemap(
        labels=labels,
        parents=parents,
        values=values,
        branchvalues="total",
        marker=dict(
            colors=color_vals,
            colorscale=[[0, T.neg], [0.5, T.surface], [1, T.pos]],
            cmin=-3.0,
            cmax=3.0,
            cmid=0.0,
            showscale=False,
            line=dict(color=T.border, width=1)
        ),
        tiling=dict(pad=4),
        texttemplate="<b>%{label}</b><br><span style='font-size:9px;'>%{customdata}</span>",
        customdata=custom_data,
        hoverinfo="label+value+percent parent"
    ))
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(t=5, b=5, l=5, r=5),
        height=650,
        dragmode='pan',
        font=dict(family="'Inter', -apple-system, sans-serif", color=T.text)
    )
    return fig

def make_advanced_chart(df: pd.DataFrame, cutoff_date, sma20_series, sma60_series, sma200_series, rsi_series, macd_line, macd_sig, macd_hist):
    fdf = df[df.index >= cutoff_date]
    if fdf.empty:
        return go.Figure()
    
    sma20 = sma20_series[sma20_series.index >= cutoff_date]
    sma60 = sma60_series[sma60_series.index >= cutoff_date]
    sma200 = sma200_series[sma200_series.index >= cutoff_date]
    rsi = rsi_series[rsi_series.index >= cutoff_date]
    macd = macd_line[macd_line.index >= cutoff_date]
    sig = macd_sig[macd_sig.index >= cutoff_date]
    hist = macd_hist[macd_hist.index >= cutoff_date]
    
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.8, 0.2]
    )
    
    # 1. Candlestick
    fig.add_trace(go.Candlestick(
        x=fdf.index, open=fdf["Open"], high=fdf["High"], low=fdf["Low"], close=fdf["Close"],
        name="Price",
        increasing=dict(line=dict(color=T.pos, width=2), fillcolor=T.pos),
        decreasing=dict(line=dict(color=T.neg, width=2), fillcolor=T.neg)
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=sma20.index, y=sma20, name="SMA 20", line=dict(color="rgba(88,166,255,0.6)", width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=sma60.index, y=sma60, name="SMA 60", line=dict(color=rgba(T.text_muted, 0.55), width=1.5)), row=1, col=1)
    if not sma200.dropna().empty:
        fig.add_trace(go.Scatter(x=sma200.index, y=sma200, name="SMA 200", line=dict(color=rgba(T.warn, 0.65), width=1.5, dash="dot")), row=1, col=1)
        
    # 2. Volume
    colors = [T.pos if cl >= op else T.neg for op, cl in zip(fdf["Open"], fdf["Close"])]
    fig.add_trace(go.Bar(
        x=fdf.index, y=fdf["Volume"],
        name="Volume", marker_color=colors, showlegend=False
    ), row=2, col=1)
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(t=10, b=10, l=10, r=10), height=550,
        dragmode='pan',
        font=dict(color=T.text_muted, family="'Inter', -apple-system, sans-serif", size=11),
        hovermode="x unified"
    )
    fig.update_xaxes(
        showgrid=True, gridcolor=T.border, showline=True, linecolor=T.border_hi, ticks="outside",
        showspikes=True, spikethickness=1, spikedash="dash", spikemode="across", spikecolor=T.text_muted
    )
    fig.update_xaxes(rangeslider_visible=False) # Hide range slider on all subplots
    fig.update_yaxes(
        showgrid=True, gridcolor=T.border, side="right", showline=True, linecolor=T.border_hi, ticks="outside",
        showspikes=True, spikethickness=1, spikedash="dash", spikemode="across", spikecolor=T.text_muted
    )
    fig.update_yaxes(tickprefix="$", row=1, col=1)
    return fig

# Callback route logic for pattern search
def route_to_cheat_sheet(pattern_name):
    st.session_state["current_tab"] = "PATTERN_GUIDE"
    st.session_state["highlighted_pattern"] = pattern_name

def set_order_buy():
    st.session_state["trade_order_type"] = "BUY"

def set_order_sell():
    st.session_state["trade_order_type"] = "SELL"

# ==============================================================================
# MAIN RENDER DELEGATION
# ==============================================================================


# ──────────────────────────────────────────────────────────────────────────────
# TAB 1: MARKET TERMINAL (MARKET HOME)
# ──────────────────────────────────────────────────────────────────────────────
if current_tab == "MARKET_HOME":
    st.markdown(
        """
        <div class="rt-section-head">
            <div>
                <div class="rt-section-title">Market Home</div>
                <div class="rt-section-sub">Live benchmarks · scanners · sector heat</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    # ── INDEX SNAPSHOT MATRIX (7 BENCHMARKS) ──
    with st.spinner("Loading indices..."):
        idx_data = get_index_snapshots()
    if idx_data:
        indices_cols = st.columns(len(idx_data))
        for idx, item in enumerate(idx_data):
            with indices_cols[idx]:
                up = item["pct"] >= 0
                sign = "+" if up else ""
                pts_sign = "+" if item["pts"] >= 0 else ""
                cc_text = "var(--rv-pos)" if up else "var(--rv-neg)"

                # Stacked, not inline. Seven benchmarks across the viewport
                # leaves ~160px per card, and the previous single-row flex put
                # name, level, points and percent side by side - they
                # overflowed into the neighbouring card ("RUSSELL 2000" landing
                # on top of the next index's change). Each figure now gets its
                # own line and the label truncates rather than pushing.
                #
                # A Streamlit border container rather than a div, because the
                # sparkline is a separate element and cannot be nested inside
                # markup - rendering the card as HTML left the chart floating
                # outside its own frame.
                with st.container(border=True):
                    st.html(f"""
                    <div class="rv-col" style="gap:2px">
                      <div class="rv-metric-label rv-truncate">{item['name']}</div>
                      <div class="rv-num" style="font-size:var(--rv-fs-figure);
                           font-weight:600;color:var(--rv-text);line-height:1.2">
                        {item['close']:,.2f}</div>
                      <div class="rv-num" style="font-size:var(--rv-fs-small);
                           font-weight:600;color:{cc_text};line-height:1.3">
                        {sign}{item['pct']:.2f}%
                        <span style="color:var(--rv-text-faint);font-weight:500">
                          {pts_sign}{item['pts']:,.2f}</span></div>
                    </div>
                    """)
                    fig = make_sparkline(item["series"], positive=up)
                    st.plotly_chart(fig, use_container_width=True,
                                    config={"displayModeBar": False})

# ── 3-COLUMN FINVIZ MATRIX GRID ──
    col1, col2, col3 = st.columns([1.1, 1.35, 1.1], gap="medium")

    with st.spinner("Scanning market momentum..."):
        scanners = get_market_scanners()

    with col1:
        st.html(fx.section_header("Top Gainers", "click a row to research"))
        with st.spinner("Scanning gainers..."):
            scanners = get_market_scanners()
        render_scanner(scanners["gainers"], "GAINER", key="scan_gainers")

        st.html(fx.section_header("Top Losers"))
        render_scanner(scanners["losers"], "LOSER", key="scan_losers")

    with col2:
        st.html(fx.section_header("Market Heatmap"))
        with st.spinner("Loading heatmap..."):
            hm_df = get_market_heatmap_data()
        if not hm_df.empty:
            st.markdown("<div class='fintech-card' style='padding:4px !important;'>", unsafe_allow_html=True)
            st.plotly_chart(make_heatmap_chart(hm_df), use_container_width=True, config={"displayModeBar": False})
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='fintech-card'><div style='color:var(--rv-text-faint); font-size:11px;'>No heatmap data</div></div>", unsafe_allow_html=True)

    with col3:
        st.html(fx.section_header("Unusual Volume"))
        render_scanner(scanners["unusual_vol"], "VOL SPIKE", key="scan_unusual")

        st.html(fx.section_header("New 52W Highs / Lows"))
        _breakouts = (
            [dict(r, signal="52W HIGH") for r in scanners["new_hi"][:5]]
            + [dict(r, signal="52W LOW") for r in scanners["new_lo"][:5]]
        )
        render_scanner(_breakouts, "BREAKOUT", key="scan_breakouts")




    # ── BOTTOM ROW WIDGETS (COMMODITIES, CRYPTO, FOREX & INSIDERS) ──
    row_futures, row_insiders = st.columns([1.5, 2.5], gap="medium")

    with row_futures:
        st.subheader("Futures, Commodities & Crypto")
        futures = get_futures_commodities()
        st.markdown("""
        <style>
            .fintech-table tr {
                transition: background-color 0.12s ease-in-out;
            }
            .fintech-table tr:hover {
                background-color: rgba(255, 255, 255, 0.03) !important;
            }
        </style>
        <div class='fintech-card' style='padding:0px !important;'>
        <table class="fintech-table" style="width:100%; border-collapse:collapse; font-size:12px; font-variant-numeric: tabular-nums;">
            <thead>
                <tr style="border-bottom:1px solid var(--rv-border); color:var(--rv-text-muted); font-size:11px; text-transform:uppercase; text-align:left;">
                    <th style="padding: 12px 14px; background-color: var(--rv-surface) !important;">Index / Future</th>
                    <th style="padding: 12px 14px; text-align:right; background-color: var(--rv-surface) !important;">Last Price</th>
                    <th style="padding: 12px 14px; text-align:right; background-color: var(--rv-surface) !important;">Change</th>
                </tr>
            </thead>
            <tbody>
        """, unsafe_allow_html=True)
        for idx, item in enumerate(futures):
            c_val = item["pct"]
            sign = "+" if c_val >= 0 else ""
            badge_style = "background-color: rgba(0, 230, 118, 0.08); color: var(--rv-pos); border: 1px solid rgba(0, 230, 118, 0.2); padding: 4px 10px; border-radius: 4px; font-weight: 700; font-family: 'JetBrains Mono', monospace;" if c_val >= 0 else "background-color: rgba(255, 23, 68, 0.08); color: var(--rv-neg); border: 1px solid rgba(255, 23, 68, 0.2); padding: 4px 10px; border-radius: 4px; font-weight: 700; font-family: 'JetBrains Mono', monospace;"
            st.markdown(f"""
                <tr style="border-bottom: 1px solid var(--rv-border);">
                    <td style="padding: 12px 14px; font-weight:700; color:var(--rv-text);">{item['name']} <span style="font-size:9px; color:var(--rv-text-muted); font-family:'JetBrains Mono', monospace;">({item['symbol']})</span></td>
                    <td style="padding: 12px 14px; text-align:right; font-weight:700; color:var(--rv-text); font-family:'JetBrains Mono', monospace;">{item['price']:,.2f}</td>
                    <td style="padding: 12px 14px; text-align:right;"><span style="{badge_style}">{sign}{c_val:.2f}%</span></td>
                </tr>
            """, unsafe_allow_html=True)
        st.markdown("</tbody></table></div>", unsafe_allow_html=True)

    with row_insiders:
        st.subheader("Recent Insider Transactions & Major Trades")
        insiders = get_recent_insiders()
        if not insiders:
            st.html(fx.empty_state(
                "No insider transaction source connected",
                "\u25c7",
                "Form 4 filings need an EDGAR or vendor feed. Nothing is shown "
                "rather than sample data."))
        else:
            st.markdown("<div class='fintech-card' style='padding:0px !important;'>", unsafe_allow_html=True)
            st.markdown("""
            <table class="fintech-table" style="width:100%; border-collapse:collapse; font-size:12px; font-variant-numeric: tabular-nums;">
                <thead>
                    <tr style="border-bottom:1px solid var(--rv-border); color:var(--rv-text-muted); font-size:11px; text-transform:uppercase; text-align:left;">
                        <th style="padding: 12px 14px; background-color: var(--rv-surface) !important;">Ticker</th>
                        <th style="padding: 12px 14px; background-color: var(--rv-surface) !important;">Insider Owner</th>
                        <th style="padding: 12px 14px; background-color: var(--rv-surface) !important;">Relationship</th>
                        <th style="padding: 12px 14px; text-align:center; background-color: var(--rv-surface) !important;">Trade</th>
                        <th style="padding: 12px 14px; text-align:right; background-color: var(--rv-surface) !important;">Cost</th>
                        <th style="padding: 12px 14px; text-align:right; background-color: var(--rv-surface) !important;">Shares</th>
                        <th style="padding: 12px 14px; text-align:right; background-color: var(--rv-surface) !important;">Value ($)</th>
                    </tr>
                </thead>
                <tbody>
            """, unsafe_allow_html=True)
            for idx, item in enumerate(insiders):
                action_style = "background-color: rgba(0, 230, 118, 0.08); color: var(--rv-pos); border: 1px solid rgba(0, 230, 118, 0.2); padding: 4px 10px; border-radius: 4px; font-weight: 800; font-size: 10px;" if item["type"] == "Buy" else "background-color: rgba(255, 23, 68, 0.08); color: var(--rv-neg); border: 1px solid rgba(255, 23, 68, 0.2); padding: 4px 10px; border-radius: 4px; font-weight: 800; font-size: 10px;"
                action_html = f'<span style="{action_style}">{item["type"].upper()}</span>'
                st.markdown(f"""
                    <tr style="border-bottom: 1px solid var(--rv-border);">
                        <td style="padding: 12px 14px; font-weight:700;"><span class="rv-ticker-link" data-rv-ticker="{item['ticker']}" data-rv-dest="RESEARCH" role="button" tabindex="0" style="color:var(--rv-info); text-decoration:none; transition: color 0.15s;">{item['ticker']}</span></td>
                        <td style="padding: 12px 14px; color:var(--rv-text);">{item['owner']}</td>
                        <td style="padding: 12px 14px; color:var(--rv-text-muted);">{item['relation']}</td>
                        <td style="padding: 12px 14px; text-align:center;">{action_html}</td>
                        <td style="padding: 12px 14px; text-align:right; font-family:'JetBrains Mono', monospace; color:var(--rv-text);">${item['price']:.2f}</td>
                        <td style="padding: 12px 14px; text-align:right; font-family:'JetBrains Mono', monospace; color:var(--rv-text);">{item['shares']:,}</td>
                        <td style="padding: 12px 14px; text-align:right; font-family:'JetBrains Mono', monospace; font-weight:700; color:var(--rv-text);">${item['value']:,.0f}</td>
                    </tr>
                """, unsafe_allow_html=True)
            st.markdown("</tbody></table></div>", unsafe_allow_html=True)

        st.subheader("Global Macro & Asset Allocation Indicators")
        st.markdown("""
        <div class="fintech-card">
            <div style="font-size:14px; font-weight:700; color:var(--rv-text); margin-bottom:8px;">⚡ Quick Prompt Triggers</div>
            <p style="color:var(--rv-text-muted); font-size:12px; line-height:1.4;">Click any prompt to instantly run technical analysis or options risk scans:</p>
        </div>
        """, unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# TAB: NEWS
# ──────────────────────────────────────────────────────────────────────────────
elif current_tab == "NEWS":
    st.subheader("Market News")
    st.caption("Live catalysts and wire headlines across major financial sources.")
    
    col_left, col_right = st.columns([2.6, 1.4], gap="medium")
    
    with st.spinner("Retrieving news wires..."):
        news = get_rss_news("^GSPC")
        
    with col_left:
        if news:
            for idx, n in enumerate(news):
                st.html(clean_html(render_rich_news_card(n, idx)))
        else:
            st.markdown("<div class='fintech-card'><div style='color:var(--rv-text-muted); font-size:12px;'>No general news available currently</div></div>", unsafe_allow_html=True)
            
    with col_right:
        st.subheader("Market Sentiment Consensus")
        if news:
            scores = [n["sentiment_score"] for n in news]
            avg_score = sum(scores) / len(scores) if scores else 0.0
            bullish_cnt = sum(1 for n in news if n["badge"] == "BULLISH")
            bearish_cnt = sum(1 for n in news if n["badge"] == "BEARISH")
            neutral_cnt = sum(1 for n in news if n["badge"] == "NEUTRAL")
            
            consensus = "MIXED"
            cc_color = "var(--rv-text-muted)"
            if avg_score > 0.05:
                consensus = "BULLISH ACCELERATION"
                cc_color = "var(--rv-pos)"
            elif avg_score < -0.05:
                consensus = "BEARISH RISK"
                cc_color = "var(--rv-neg)"
                
            st.markdown(f"""
            <div class="fintech-card" style="margin-bottom:12px;">
                <div style="font-size:10px; color:var(--rv-text-muted); font-weight:700; text-transform:uppercase; margin-bottom:4px;">Average Score Consensus</div>
                <div style="font-size:24px; font-weight:800; color:{cc_color}; font-family:'JetBrains Mono', monospace; margin-bottom:4px;">{avg_score:+.2f}</div>
                <div style="font-size:12px; font-weight:700; color:{cc_color};">{consensus}</div>
                
                <div style="border-top:1px solid var(--rv-border); margin-top:12px; padding-top:12px; display:flex; justify-content:space-between; font-size:11px; font-family:'JetBrains Mono', monospace;">
                    <div><span style="color:var(--rv-pos); font-weight:700;">{bullish_cnt}</span> Bullish</div>
                    <div><span style="color:var(--rv-text-muted); font-weight:700;">{neutral_cnt}</span> Neutral</div>
                    <div><span style="color:var(--rv-neg); font-weight:700;">{bearish_cnt}</span> Bearish</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Simple Plotly Gauge Chart for Sentiment
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = avg_score,
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "Sentiment Index", 'font': {'size': 11, 'color': 'var(--rv-text-muted)'}},
                number = {'font': {'color': 'var(--rv-text)', 'size': 14}},
                gauge = {
                    'axis': {'range': [-1, 1], 'tickwidth': 1, 'tickcolor': "var(--rv-text-muted)"},
                    'bar': {'color': cc_color},
                    'bgcolor': T.surface_alt,
                    'borderwidth': 1,
                    'bordercolor': "var(--rv-border)",
                    'steps': [
                        {'range': [-1, -0.05], 'color': 'rgba(255, 59, 48, 0.1)'},
                        {'range': [-0.05, 0.05], 'color': 'rgba(138, 148, 166, 0.1)'},
                        {'range': [0.05, 1], 'color': 'rgba(0, 200, 5, 0.1)'}
                    ]
                }
            ))
            fig_gauge.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(t=5, b=5, l=10, r=10), height=140
            )
            st.markdown("<div class='fintech-card' style='padding:4px !important; margin-bottom:12px;'>", unsafe_allow_html=True)
            st.plotly_chart(fig_gauge, use_container_width=True, config={"displayModeBar": False})
            st.markdown("</div>", unsafe_allow_html=True)
            
        st.subheader("Trending Watchlist & Market Leaders")
        trending_tickers = [
            "NVDA", "TSLA", "AAPL", "PLTR", "MSFT", "AMD", "AMZN", "META",
            "GOOGL", "NFLX", "JPM", "V", "AVGO", "SMCI", "ARM", "COIN",
            "BAC", "LLY", "UNH", "DIS"
        ]

        with st.spinner("Syncing watchlist..."):
            tr_prices = get_live_prices_batch(trending_tickers)
        st.markdown("<div class='fintech-card' style='padding:0px !important;'>", unsafe_allow_html=True)
        st.markdown("""
        <table class="fintech-table" style="width:100%; border-collapse:collapse; font-size:12px; font-variant-numeric: tabular-nums;">
            <thead>
                <tr style="border-bottom:1px solid var(--rv-border); color:var(--rv-text-muted); font-size:11px; text-transform:uppercase; text-align:left;">
                    <th style="padding: 12px 14px; background-color: var(--rv-surface) !important;">Symbol</th>
                    <th style="padding: 12px 14px; text-align:right; background-color: var(--rv-surface) !important;">Last Price</th>
                    <th style="padding: 12px 14px; text-align:right; background-color: var(--rv-surface) !important;">Change</th>
                </tr>
            </thead>
            <tbody>
        """, unsafe_allow_html=True)
        for tk in trending_tickers:
            info = get_ticker_info(tk)
            chg = info.get("day_change_pct")
            price = tr_prices.get(tk) or info.get("previous_close")
            badge_style = ("background-color: var(--rv-pos-soft); color: var(--rv-pos); "
                           "border: 1px solid var(--rv-pos); padding: 4px 10px; border-radius: 4px; "
                           "font-weight: 700; font-family: 'JetBrains Mono', monospace;") if (chg or 0) >= 0 else (
                          "background-color: var(--rv-neg-soft); color: var(--rv-neg); "
                          "border: 1px solid var(--rv-neg); padding: 4px 10px; border-radius: 4px; "
                          "font-weight: 700; font-family: 'JetBrains Mono', monospace;")
            if chg is None:
                badge_style = ("background-color: var(--rv-surface-hi); color: var(--rv-text-faint); "
                               "padding: 4px 10px; border-radius: 4px; font-weight: 600;")
            st.markdown(f"""
                <tr style="border-bottom: 1px solid var(--rv-border);">
                    <td style="padding: 12px 14px; font-weight:700;"><span class="rv-ticker-link" data-rv-ticker="{tk}" data-rv-dest="RESEARCH" role="button" tabindex="0" style="color:var(--rv-info); text-decoration:none; transition: color 0.15s;">{tk}</span></td>
                    <td style="padding: 12px 14px; text-align:right; font-weight:700; color:var(--rv-text); font-family:'JetBrains Mono', monospace;">{fmt_money(price)}</td>
                    <td style="padding: 12px 14px; text-align:right;"><span style="{badge_style}">{fmt_pct(chg)}</span></td>
                </tr>
            """, unsafe_allow_html=True)
        st.markdown("</tbody></table></div>", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
elif current_tab == "MARKETS":
    s1, s2 = st.columns([1.8, 2.2])
    with s1:
        st.subheader("Sector Performance Table")
        with st.spinner("Loading sector indexes..."):
            sectors = get_sector_performance()
        if sectors:
            st.markdown("<div class='fintech-card' style='padding:0px !important;'>", unsafe_allow_html=True)
            st.markdown("""
            <table class="fintech-table" style="width:100%; border-collapse:collapse; font-size:12px; font-variant-numeric: tabular-nums;">
                <thead>
                    <tr style="border-bottom:1px solid var(--rv-border); color:var(--rv-text-muted); font-size:11px; text-transform:uppercase; text-align:left;">
                        <th style="padding: 12px 14px; background-color: var(--rv-surface) !important;">Sector / ETF</th>
                        <th style="padding: 12px 14px; text-align:center; background-color: var(--rv-surface) !important;">Momentum</th>
                        <th style="padding: 12px 14px; text-align:right; background-color: var(--rv-surface) !important;">1D Return</th>
                    </tr>
                </thead>
                <tbody>
            """, unsafe_allow_html=True)
            for item in sectors:
                c = item["change"]
                mom = item["momentum"]
                sign = "+" if c >= 0 else ""
                mom_color = "var(--rv-pos)" if mom == "UP" else ("var(--rv-neg)" if mom == "DOWN" else "var(--rv-text-muted)")
                badge_style = "background-color: rgba(0, 230, 118, 0.08); color: var(--rv-pos); border: 1px solid rgba(0, 230, 118, 0.2); padding: 4px 10px; border-radius: 4px; font-weight: 700; font-family: 'JetBrains Mono', monospace;" if c >= 0 else "background-color: rgba(255, 23, 68, 0.08); color: var(--rv-neg); border: 1px solid rgba(255, 23, 68, 0.2); padding: 4px 10px; border-radius: 4px; font-weight: 700; font-family: 'JetBrains Mono', monospace;"
                st.markdown(f"""
                    <tr style="border-bottom: 1px solid var(--rv-border);">
                        <td style="padding: 12px 14px; font-weight:700;"><span style="color:var(--rv-info);">{item['name']}</span> <span style="font-size:10px; color:var(--rv-text-muted); font-family:'JetBrains Mono', monospace;">({item['ticker']})</span></td>
                        <td style="padding: 12px 14px; text-align:center; font-weight:700; color:{mom_color};">{mom}</td>
                        <td style="padding: 12px 14px; text-align:right;"><span style="{badge_style}">{sign}{c:.2f}%</span></td>
                    </tr>
                """, unsafe_allow_html=True)
            st.markdown("</tbody></table></div>", unsafe_allow_html=True)

    with s2:
        st.subheader("Market Breadth & Sector Trends")
        with st.spinner("Calculating breadth index..."):
            breadth = get_market_breadth_index()
        if breadth.get("valid"):
            st.markdown("<div class='fintech-card' style='padding:12px; margin-bottom: 12px;'>", unsafe_allow_html=True)
            
            # Gauge Plotly Chart
            fig_breadth = make_subplots(rows=1, cols=2, specs=[[{'type': 'indicator'}, {'type': 'indicator'}]], horizontal_spacing=0.1)
            
            # Short-Term 20D Gauge
            fig_breadth.add_trace(go.Indicator(
                mode="gauge+number",
                value=breadth['pct_20'],
                number={'suffix': "%", 'font': {'color': 'var(--rv-text)', 'size': 18, 'family': 'JetBrains Mono'}},
                title={'text': "Short-Term (20D SMA)", 'font': {'size': 10, 'color': 'var(--rv-text-muted)'}},
                gauge={
                    'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': 'var(--rv-text-muted)'},
                    'bar': {'color': 'var(--rv-pos)'},
                    'bgcolor': T.surface_alt,
                    'borderwidth': 1,
                    'bordercolor': "var(--rv-border)",
                    'steps': [
                        {'range': [0, 30], 'color': 'rgba(255, 59, 48, 0.1)'},
                        {'range': [30, 70], 'color': 'rgba(138, 148, 166, 0.1)'},
                        {'range': [70, 100], 'color': 'rgba(0, 200, 5, 0.1)'}
                    ]
                }
            ), row=1, col=1)
            
            # Medium-Term 60D Gauge
            fig_breadth.add_trace(go.Indicator(
                mode="gauge+number",
                value=breadth['pct_60'],
                number={'suffix': "%", 'font': {'color': 'var(--rv-text)', 'size': 18, 'family': 'JetBrains Mono'}},
                title={'text': "Medium-Term (60D SMA)", 'font': {'size': 10, 'color': 'var(--rv-text-muted)'}},
                gauge={
                    'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': 'var(--rv-text-muted)'},
                    'bar': {'color': 'var(--rv-info)'},
                    'bgcolor': T.surface_alt,
                    'borderwidth': 1,
                    'bordercolor': "var(--rv-border)",
                    'steps': [
                        {'range': [0, 30], 'color': 'rgba(255, 59, 48, 0.1)'},
                        {'range': [30, 70], 'color': 'rgba(138, 148, 166, 0.1)'},
                        {'range': [70, 100], 'color': 'rgba(88, 166, 255, 0.1)'}
                    ]
                }
            ), row=1, col=2)
            
            fig_breadth.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(t=30, b=20, l=30, r=30), height=170
            )
            st.plotly_chart(fig_breadth, use_container_width=True, config={"displayModeBar": False})
            st.markdown("</div>", unsafe_allow_html=True)

        if sectors:
            # Horizontal Bar Chart for sectors returns
            names = [item["name"] for item in sectors]
            returns = [item["change"] for item in sectors]
            colors = [T.pos if r >= 0 else T.neg for r in returns]
            fig_sector = go.Figure(go.Bar(
                x=returns, y=names, orientation='h',
                marker_color=colors, showlegend=False
            ))
            fig_sector.update_layout(
                title=dict(text="Sector Returns (1D Change)", font=dict(size=12, color=T.text_muted)),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(t=35, b=5, l=5, r=5), height=230
            )
            fig_sector.update_xaxes(showgrid=True, gridcolor=T.border, showline=True, linecolor=T.border_hi, ticks="outside")
            fig_sector.update_yaxes(showgrid=False, showline=True, linecolor=T.border_hi)
            st.markdown("<div class='fintech-card' style='padding:6px !important;'>", unsafe_allow_html=True)
            st.plotly_chart(fig_sector, use_container_width=True, config={"displayModeBar": False})
            st.markdown("</div>", unsafe_allow_html=True)

    # ── MARKET MOVERS SCANNER COLUMNS ──
    st.subheader("Market Movers & Scanners")
    with st.spinner("Calculating scanners..."):
        scanners = get_market_scanners()
        
    m_col1, m_col2, m_col3 = st.columns(3)
    
    with m_col1:
        st.markdown("##### Daily Top Gainers")
        st.markdown("<div class='fintech-card' style='padding:0px !important;'>", unsafe_allow_html=True)
        st.markdown("""
        <table class="fintech-table" style="width:100%; border-collapse:collapse; font-size:11px; font-variant-numeric: tabular-nums;">
            <thead>
                <tr style="border-bottom:1px solid var(--rv-border); color:var(--rv-text-muted); text-transform:uppercase;">
                    <th style="padding: 10px 12px; text-align:left; background-color: var(--rv-surface) !important;">Ticker</th>
                    <th style="padding: 10px 12px; text-align:right; background-color: var(--rv-surface) !important;">Price</th>
                    <th style="padding: 10px 12px; text-align:right; background-color: var(--rv-surface) !important;">Change</th>
                </tr>
            </thead>
            <tbody>
        """, unsafe_allow_html=True)
        for r in scanners["gainers"][:10]:
            chg = r["change"]
            badge_style = "background-color: rgba(0, 230, 118, 0.08); color: var(--rv-pos); border: 1px solid rgba(0, 230, 118, 0.2); padding: 3px 6px; border-radius: 4px; font-weight: 700; font-family: 'JetBrains Mono', monospace;"
            st.markdown(f"""
                <tr style="border-bottom: 1px solid var(--rv-border);">
                    <td style="padding: 10px 12px; font-weight:700;"><span class="rv-ticker-link" data-rv-ticker="{r['ticker']}" data-rv-dest="RESEARCH" role="button" tabindex="0" style="color:var(--rv-info); text-decoration:none;">{r['ticker']}</span></td>
                    <td style="padding: 10px 12px; text-align:right; color:var(--rv-text); font-family:'JetBrains Mono', monospace;">${r['close']:.2f}</td>
                    <td style="padding: 10px 12px; text-align:right;"><span style="{badge_style}">+{chg:.2f}%</span></td>
                </tr>
            """, unsafe_allow_html=True)
        st.markdown("</tbody></table></div>", unsafe_allow_html=True)

    with m_col2:
        st.markdown("##### Daily Top Losers")
        st.markdown("<div class='fintech-card' style='padding:0px !important;'>", unsafe_allow_html=True)
        st.markdown("""
        <table class="fintech-table" style="width:100%; border-collapse:collapse; font-size:11px; font-variant-numeric: tabular-nums;">
            <thead>
                <tr style="border-bottom:1px solid var(--rv-border); color:var(--rv-text-muted); text-transform:uppercase;">
                    <th style="padding: 10px 12px; text-align:left; background-color: var(--rv-surface) !important;">Ticker</th>
                    <th style="padding: 10px 12px; text-align:right; background-color: var(--rv-surface) !important;">Price</th>
                    <th style="padding: 10px 12px; text-align:right; background-color: var(--rv-surface) !important;">Change</th>
                </tr>
            </thead>
            <tbody>
        """, unsafe_allow_html=True)
        for r in scanners["losers"][:10]:
            chg = r["change"]
            badge_style = "background-color: rgba(255, 23, 68, 0.08); color: var(--rv-neg); border: 1px solid rgba(255, 23, 68, 0.2); padding: 3px 6px; border-radius: 4px; font-weight: 700; font-family: 'JetBrains Mono', monospace;"
            st.markdown(f"""
                <tr style="border-bottom: 1px solid var(--rv-border);">
                    <td style="padding: 10px 12px; font-weight:700;"><span class="rv-ticker-link" data-rv-ticker="{r['ticker']}" data-rv-dest="RESEARCH" role="button" tabindex="0" style="color:var(--rv-info); text-decoration:none;">{r['ticker']}</span></td>
                    <td style="padding: 10px 12px; text-align:right; color:var(--rv-text); font-family:'JetBrains Mono', monospace;">${r['close']:.2f}</td>
                    <td style="padding: 10px 12px; text-align:right;"><span style="{badge_style}">{chg:.2f}%</span></td>
                </tr>
            """, unsafe_allow_html=True)
        st.markdown("</tbody></table></div>", unsafe_allow_html=True)

    with m_col3:
        st.markdown("##### High Volume Leaders")
        st.markdown("<div class='fintech-card' style='padding:0px !important;'>", unsafe_allow_html=True)
        st.markdown("""
        <table class="fintech-table" style="width:100%; border-collapse:collapse; font-size:11px; font-variant-numeric: tabular-nums;">
            <thead>
                <tr style="border-bottom:1px solid var(--rv-border); color:var(--rv-text-muted); text-transform:uppercase;">
                    <th style="padding: 10px 12px; text-align:left; background-color: var(--rv-surface) !important;">Ticker</th>
                    <th style="padding: 10px 12px; text-align:right; background-color: var(--rv-surface) !important;">Price</th>
                    <th style="padding: 10px 12px; text-align:right; background-color: var(--rv-surface) !important;">Volume</th>
                </tr>
            </thead>
            <tbody>
        """, unsafe_allow_html=True)
        for r in scanners["unusual_vol"][:10]:
            vol_str = format_volume(r["volume"])
            st.markdown(f"""
                <tr style="border-bottom: 1px solid var(--rv-border);">
                    <td style="padding: 10px 12px; font-weight:700;"><span class="rv-ticker-link" data-rv-ticker="{r['ticker']}" data-rv-dest="RESEARCH" role="button" tabindex="0" style="color:var(--rv-info); text-decoration:none;">{r['ticker']}</span></td>
                    <td style="padding: 10px 12px; text-align:right; color:var(--rv-text); font-family:'JetBrains Mono', monospace;">${r['close']:.2f}</td>
                    <td style="padding: 10px 12px; text-align:right; color:var(--rv-text-muted); font-family:'JetBrains Mono', monospace; font-weight:700;">{vol_str}</td>
                </tr>
            """, unsafe_allow_html=True)
        st.markdown("</tbody></table></div>", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# TAB 5: AI AGENT RESEARCH
# ──────────────────────────────────────────────────────────────────────────────
elif current_tab == "RESEARCH":
    # Search controls
    st.subheader("Stock Search")
    sr1, sr2, sr3 = st.columns([3, 1, 1])
    with sr1:
        ticker_input = st.text_input("Ticker Symbol", value=st.session_state.active_ticker, key="ticker_input_search", label_visibility="collapsed")
    with sr2:
        chart_period = st.selectbox("Timeframe", ["1 Month", "3 Months", "6 Months", "1 Year"], index=2, key="timeframe_search", label_visibility="collapsed")
    with sr3:
        run_agent = st.button("Run Analytics", width="stretch", key="run_agent_search")

    # Run analysis block
    if run_agent or "results" not in st.session_state or not st.session_state["results"]:
        symbol = ticker_input.strip().upper()
        if symbol:
            st.session_state["active_ticker"] = symbol
            with st.spinner(f"Analyzing {symbol}..."):
                try:
                    data = get_stock_data(symbol)
                    if data["success"]:
                        analysis = run_analysis(symbol, data)
                        if analysis["success"]:
                            agent_result = evaluate_ticker(analysis)
                            analysis.update(agent_result)
                            analysis["prices"] = data["prices"]
                            quant = process_advanced_analytics(symbol, analysis)
                            analysis.update(quant)
                            st.session_state["results"] = [analysis]
                            generate_markdown_report(st.session_state["results"], "stock_research_report.md")
                        else:
                            st.error(analysis["error_message"])
                    else:
                        st.error(data["error_message"])
                except Exception as e:
                    st.error(str(e))

    # Show results
    res_list = st.session_state.get("results", [])
    if res_list and res_list[0].get("success"):
        res = res_list[0]
        sym = res["symbol"]
        cl = res["last_close"]
        ch = res["day_change_pct"]
        act = res.get("action_label", "HOLD")
        acls = res.get("action_class", "badge-hold")
        sign = "+" if ch > 0 else ""

        # Safe Info Lookup
        info = get_ticker_info(sym)

        # Header banner
        pill_color = "rgba(0, 200, 5, 0.15)" if ch >= 0 else "rgba(255, 59, 48, 0.15)"
        text_color = "var(--rv-pos)" if ch >= 0 else "var(--rv-neg)"
        
        st.markdown(f"""
        <div class="fintech-card">
            <div style="display:flex; align-items:baseline; gap:16px;">
                <span style="font-size:24px; font-weight:700; color:var(--rv-text);">{sym}</span>
                <span style="font-size:14px; color:var(--rv-text-muted);">{info['long_name']}</span>
                <span style="font-size:28px; font-weight:700; color:var(--rv-text);">${cl:.2f}</span>
                <span style="background-color:{pill_color}; color:{text_color}; padding:4px 8px; border-radius:4px; font-weight:600; font-size:13px;">{sign}{ch:.2f}%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Download Report
        if os.path.exists("stock_research_report.md"):
            with open("stock_research_report.md", "r") as f:
                report_data = f.read()
            st.download_button(
                label="Download Research Report (Markdown)",
                data=report_data,
                file_name=f"{sym}_research_report.md",
                mime="text/markdown"
            )

        # 4-Column statistics matrix (Yahoo Finance table style)
        vol_pct = res.get('volatility', 0.0)
        st.markdown(f"""
        <div class="fintech-card" style="padding: 12px !important; margin-bottom: 8px !important;">
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;">
                <!-- Column 1 -->
                <table style="width: 100%; border: none !important; border-collapse: collapse !important;">
                    <tr style="border-bottom: 1px solid var(--rv-border);">
                        <td style="color: var(--rv-text-muted); padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">Previous Close</td>
                        <td style="text-align: right; color: var(--rv-text); font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">${info['previous_close']:.2f}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--rv-border);">
                        <td style="color: var(--rv-text-muted); padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">Open Price</td>
                        <td style="text-align: right; color: var(--rv-text); font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">${info['open']:.2f}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--rv-border);">
                        <td style="color: var(--rv-text-muted); padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">Bid Price</td>
                        <td style="text-align: right; color: var(--rv-text); font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">${info['bid']:.2f}</td>
                    </tr>
                    <tr>
                        <td style="color: var(--rv-text-muted); padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">Ask Price</td>
                        <td style="text-align: right; color: var(--rv-text); font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">${info['ask']:.2f}</td>
                    </tr>
                </table>
                <!-- Column 2 -->
                <table style="width: 100%; border: none !important; border-collapse: collapse !important;">
                    <tr style="border-bottom: 1px solid var(--rv-border);">
                        <td style="color: var(--rv-text-muted); padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">Day's Range</td>
                        <td style="text-align: right; color: var(--rv-text); font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums; font-size: 11px;">${info['day_low']:.2f} - ${info['day_high']:.2f}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--rv-border);">
                        <td style="color: var(--rv-text-muted); padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">52-Week Range</td>
                        <td style="text-align: right; color: var(--rv-text); font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums; font-size: 11px;">${info['fifty_two_low']:.2f} - ${info['fifty_two_high']:.2f}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--rv-border);">
                        <td style="color: var(--rv-text-muted); padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">Volume</td>
                        <td style="text-align: right; color: var(--rv-text); font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">{format_volume(info['volume'])}</td>
                    </tr>
                    <tr>
                        <td style="color: var(--rv-text-muted); padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">Avg Volume</td>
                        <td style="text-align: right; color: var(--rv-text); font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">{format_volume(info['avg_volume'])}</td>
                    </tr>
                </table>
                <!-- Column 3 -->
                <table style="width: 100%; border: none !important; border-collapse: collapse !important;">
                    <tr style="border-bottom: 1px solid var(--rv-border);">
                        <td style="color: var(--rv-text-muted); padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">Market Cap</td>
                        <td style="text-align: right; color: var(--rv-text); font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">{format_market_cap(info['market_cap'])}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--rv-border);">
                        <td style="color: var(--rv-text-muted); padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">Beta (5Y)</td>
                        <td style="text-align: right; color: var(--rv-text); font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">{info['beta']:.2f}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--rv-border);">
                        <td style="color: var(--rv-text-muted); padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">PE Ratio</td>
                        <td style="text-align: right; color: var(--rv-text); font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">{info['pe_ratio']:.2f}</td>
                    </tr>
                    <tr>
                        <td style="color: var(--rv-text-muted); padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">EPS (TTM)</td>
                        <td style="text-align: right; color: var(--rv-text); font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">${info['eps']:.2f}</td>
                    </tr>
                </table>
                <!-- Column 4 -->
                <table style="width: 100%; border: none !important; border-collapse: collapse !important;">
                    <tr style="border-bottom: 1px solid var(--rv-border);">
                        <td style="color: var(--rv-text-muted); padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">14-Day RSI</td>
                        <td style="text-align: right; color: var(--rv-text); font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">{res.get('rsi', 50.0):.1f}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--rv-border);">
                        <td style="color: var(--rv-text-muted); padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">20-Day SMA</td>
                        <td style="text-align: right; color: var(--rv-text); font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">${res.get('sma_20', 0.0):.2f}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid var(--rv-border);">
                        <td style="color: var(--rv-text-muted); padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">60-Day SMA</td>
                        <td style="text-align: right; color: var(--rv-text); font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">${res.get('sma_60', 0.0):.2f}</td>
                    </tr>
                    <tr>
                        <td style="color: var(--rv-text-muted); padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">Annualized Vol</td>
                        <td style="text-align: right; color: var(--rv-text); font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">{vol_pct:.1f}%</td>
                    </tr>
                </table>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Algorithmic Guidance Matrix
        guidance_label = act
        g_color = "var(--rv-pos)" if "BUY" in guidance_label else ("var(--rv-neg)" if "SELL" in guidance_label or "REDUCE" in guidance_label else "var(--rv-text-muted)")
        
        # Breakdown computations
        ma_diff = ((cl - res["sma_20"]) / res["sma_20"]) * 100 if res["sma_20"] > 0 else 0.0
        direction = "above" if ma_diff >= 0 else "below"
        boundary_state = "upward" if ma_diff >= 0 else "downward"
        s_total = res.get("s_total", 0.0)
        sentiment_direction = "bullish (positive)" if s_total > 0 else ("bearish (negative)" if s_total < 0 else "neutral")
        
        summary_sentence = f"""
        <b>Short-Term Trend</b>: {sym} is trading <b>{direction}</b> its 20-day average price of ${res.get('sma_20', 0.0):.2f} by <b>{abs(ma_diff):.1f}%</b>. This indicates short-term <b>{boundary_state}</b> momentum.<br><br>
        <b>News Sentiment</b>: Publisher consensus is <b>{sentiment_direction.upper()}</b> with a score of <b>{s_total:+.2f}</b>, reflecting generally favorable headlines and positive market expectations.
        """

        vol = res.get("volatility", 0.0)
        vol_cap = min(25.0, (10.0 / (vol + 1e-9)) * 100) if vol > 0 else 0.0

        rcol1, rcol2 = st.columns([1, 2])
        with rcol1:
            st.markdown(f"""
            <div class="fintech-card" style="text-align:center; min-height: 120px;">
                <div style="font-size:10px; color:var(--rv-text-muted); font-weight:600; text-transform:uppercase;">Algorithmic Guidance</div>
                <div style="font-size:24px; font-weight:800; color:{g_color}; margin-top:8px;">{guidance_label}</div>
            </div>
            """, unsafe_allow_html=True)
        with rcol2:
            st.markdown(f"""
            <div class="fintech-card" style="min-height: 120px;">
                <div style="font-size:10px; color:var(--rv-text-muted); font-weight:600; text-transform:uppercase; margin-bottom:4px;">Micro-Summarization Breakdown</div>
                <div style="font-size:12px; color:var(--rv-text); line-height:1.4;">{summary_sentence}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="fintech-card" style="border-left: 3px solid var(--rv-pos); padding: 10px !important;">
            <div style="font-size:13px; color:var(--rv-text); font-weight:600;">Risk Protocol Status: Current asset exhibits a calculated 60-day annualized volatility metric of {vol:.1f}%. The position-sizing engine advises capping your theoretical capital deployment to exactly {vol_cap:.1f}% of total available portfolio equity balance sheets to shield capital from sudden price flips.</div>
        </div>
        """, unsafe_allow_html=True)

        # Advanced multi-pane Plotly Subplot
        df_prices = res["prices"]
        sma20_ser = df_prices["Close"].rolling(20).mean()
        sma60_ser = df_prices["Close"].rolling(60).mean()
        sma200_ser = df_prices["Close"].rolling(200).mean()
        
        # Subplot calculation values
        macd_val, macd_sig, macd_hist = calculate_macd(df_prices["Close"])
        ema12 = calculate_ema(df_prices["Close"], 12)
        ema26 = calculate_ema(df_prices["Close"], 26)
        macd_line = ema12 - ema26
        macd_sig_line = calculate_ema(macd_line, 9)
        macd_hist_line = macd_line - macd_sig_line
        
        rsi_series = df_prices["Close"].copy()
        for idx in range(len(df_prices)):
            sub_ser = df_prices["Close"].iloc[:idx+1]
            rsi_series.iloc[idx] = calculate_rsi(sub_ser, 14)
            
        now = df_prices.index[-1]
        if chart_period == "1 Month": cutoff = now - timedelta(days=30)
        elif chart_period == "3 Months": cutoff = now - timedelta(days=90)
        elif chart_period == "6 Months": cutoff = now - timedelta(days=180)
        else: cutoff = now - timedelta(days=365)

        fig_advanced = make_advanced_chart(df_prices, cutoff, sma20_ser, sma60_ser, sma200_ser, rsi_series, macd_line, macd_sig_line, macd_hist_line)
        st.markdown("<div class='fintech-card' style='padding:6px !important;'>", unsafe_allow_html=True)
        st.plotly_chart(fig_advanced, use_container_width=True, config={"displayModeBar": True, "scrollZoom": True})
        st.markdown("</div>", unsafe_allow_html=True)

        # ──────────────────────────────────────────────────────────────────────
        # PREDICTIVE AI MODEL FORECAST & ML DIAGNOSTICS
        # ──────────────────────────────────────────────────────────────────────
        st.subheader("Predictive AI Forecast (30-Day Trajectory & Feature Importance)")
        forecast_data = res.get("ml_forecast") or []
        feat_imps = res.get("ml_feature_importances") or []

        ml_col1, ml_col2 = st.columns([1.8, 1.2])
        with ml_col1:
            if forecast_data:
                fig_ml_forecast = make_ml_prediction_chart(forecast_data, cl, sym)
                st.markdown("<div class='fintech-card' style='padding:6px !important;'>", unsafe_allow_html=True)
                st.plotly_chart(fig_ml_forecast, use_container_width=True, config={"displayModeBar": False})
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.info("Insufficient historical bars to render predictive trajectory.")

        with ml_col2:
            if feat_imps:
                fig_feat_imp = make_feature_importance_chart(feat_imps)
                st.markdown("<div class='fintech-card' style='padding:6px !important;'>", unsafe_allow_html=True)
                st.plotly_chart(fig_feat_imp, use_container_width=True, config={"displayModeBar": False})
                st.markdown("</div>", unsafe_allow_html=True)

        # ML Performance Metrics Cards
        ml_prob = res.get("ml_bullish_prob", 50.0)
        ml_acc = res.get("ml_accuracy_pct", 60.0)
        ml_pred = res.get("ml_prediction", "Neutral")
        ml_conf = res.get("ml_confidence_pct", 60)

        p_color = "#00C805" if ml_pred == "Bullish" else ("#FF3B30" if ml_pred == "Bearish" else "#8A94A6")

        st.markdown(f"""
        <div class="fintech-card" style="padding:12px !important; margin-bottom:14px !important;">
            <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:12px; text-align:center;">
                <div>
                    <div style="font-size:10px; color:#8A94A6; text-transform:uppercase; font-weight:600;">ML Target Direction</div>
                    <div style="font-size:18px; font-weight:800; color:{p_color}; margin-top:3px;">{ml_pred}</div>
                </div>
                <div>
                    <div style="font-size:10px; color:#8A94A6; text-transform:uppercase; font-weight:600;">Bullish Gain Probability</div>
                    <div style="font-size:18px; font-weight:800; color:#FFFFFF; font-family:'JetBrains Mono', monospace; margin-top:3px;">{ml_prob:.1f}%</div>
                </div>
                <div>
                    <div style="font-size:10px; color:#8A94A6; text-transform:uppercase; font-weight:600;">Backtest Hit Rate (Acc)</div>
                    <div style="font-size:18px; font-weight:800; color:#58A6FF; font-family:'JetBrains Mono', monospace; margin-top:3px;">{ml_acc:.1f}%</div>
                </div>
                <div>
                    <div style="font-size:10px; color:#8A94A6; text-transform:uppercase; font-weight:600;">Model Confidence</div>
                    <div style="font-size:18px; font-weight:800; color:#00E676; font-family:'JetBrains Mono', monospace; margin-top:3px;">{ml_conf}%</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.subheader("Industry Peer Comparison")

        # Select peers
        peer_mapping = {
            "AAPL": ["MSFT", "GOOGL", "META"],
            "MSFT": ["AAPL", "GOOGL", "AMZN"],
            "NVDA": ["AMD", "INTC", "QCOM"],
            "TSLA": ["F", "GM", "RIVN"],
            "AMZN": ["WMT", "TGT", "EBAY"],
            "META": ["SNAP", "PINS", "MSFT"],
            "GOOGL": ["MSFT", "META", "AAPL"],
            "NFLX": ["DIS", "WBD", "PARA"]
        }
        peers = peer_mapping.get(sym, ["AAPL", "MSFT", "NVDA"])
        peer_symbols = [sym] + peers
        with st.spinner("Syncing peer metrics..."):
            peer_prices = get_live_prices_batch(peer_symbols)
        
        st.markdown("<div class='fintech-card' style='padding:0px !important; margin-bottom: 12px;'>", unsafe_allow_html=True)
        st.markdown("""
        <table style="width:100%; border-collapse:collapse; font-size:12px; font-variant-numeric: tabular-nums;">
            <thead>
                <tr style="border-bottom:1px solid var(--rv-border-hi); color:var(--rv-text-muted); font-size:11px; text-transform:uppercase; text-align:left;">
                    <th style="padding: 8px 12px;">Symbol</th>
                    <th style="padding: 8px 12px;">Company Name</th>
                    <th style="padding: 8px 12px; text-align:right;">Last Price</th>
                    <th style="padding: 8px 12px; text-align:right;">1D Return</th>
                    <th style="padding: 8px 12px; text-align:right;">P/E Ratio</th>
                    <th style="padding: 8px 12px; text-align:right;">Market Cap</th>
                </tr>
            </thead>
            <tbody>
        """, unsafe_allow_html=True)
        for psym in peer_symbols:
            pinfo = get_ticker_info(psym)
            p_close = peer_prices.get(psym) or pinfo.get("previous_close")
            p_chg = pinfo.get("day_change_pct")
            p_pe = pinfo.get("pe_ratio")
            p_cap = pinfo.get("market_cap")

            badge_style = ("background-color: var(--rv-pos-soft); color: var(--rv-pos); padding: 4px 8px; "
                           "border-radius: 4px; font-weight: 700; font-family: 'JetBrains Mono', monospace;"
                           ) if (p_chg or 0) >= 0 else (
                          "background-color: var(--rv-neg-soft); color: var(--rv-neg); padding: 4px 8px; "
                          "border-radius: 4px; font-weight: 700; font-family: 'JetBrains Mono', monospace;")
            if p_chg is None:
                badge_style = ("background-color: var(--rv-surface-hi); color: var(--rv-text-faint); "
                               "padding: 4px 8px; border-radius: 4px; font-weight: 600;")
            
            is_active = (psym == sym)
            td_bg = "background-color: rgba(0, 230, 118, 0.08);" if is_active else ""
            border_left = "border-left: 4px solid var(--rv-pos);" if is_active else ""
            font_weight = "font-weight: 800;" if is_active else "font-weight: 600;"
            
            st.markdown(f"""
                <tr style="border-bottom: 1px solid var(--rv-border);">
                    <td style="padding: 12px 14px; {td_bg} {border_left} color:var(--rv-info); {font_weight}">{psym}</td>
                    <td style="padding: 12px 14px; {td_bg} color:var(--rv-text); {font_weight}">{pinfo.get('long_name', psym)}</td>
                    <td style="padding: 12px 14px; {td_bg} text-align:right; color:var(--rv-text); {font_weight} font-family:'JetBrains Mono', monospace;">{fmt_money(p_close)}</td>
                    <td style="padding: 12px 14px; {td_bg} text-align:right;"><span style="{badge_style}">{fmt_pct(p_chg)}</span></td>
                    <td style="padding: 12px 14px; {td_bg} text-align:right; color:var(--rv-text); {font_weight} font-family:'JetBrains Mono', monospace;">{f"{p_pe:.1f}x" if p_pe else "\u2014"}</td>
                    <td style="padding: 12px 14px; {td_bg} text-align:right; color:var(--rv-text); {font_weight} font-family:'JetBrains Mono', monospace;">{fmt_cap(p_cap)}</td>
                </tr>
            """, unsafe_allow_html=True)
        st.markdown("</tbody></table></div>", unsafe_allow_html=True)

        pats = detect_patterns(df_prices)
        if pats:
            st.markdown("<div class='fintech-card'>", unsafe_allow_html=True)
            st.markdown("<div style='font-size:10px; color:var(--rv-text-muted); font-weight:600; text-transform:uppercase; margin-bottom:4px;'>Detected Formations</div>", unsafe_allow_html=True)
            for p in pats:
                st.markdown(f"<span style='color:var(--rv-pos); font-weight:700; margin-right:12px;'>{p}</span>", unsafe_allow_html=True)
                st.button(f"Go to {p} Pattern Guide", key=f"lnk_{sym}_{p}", on_click=route_to_cheat_sheet, args=(p,))
            st.markdown("</div>", unsafe_allow_html=True)

        # News Feed specific to ticker
        rss_news = get_rss_news(sym)
        if rss_news:
            st.subheader("News Headlines and Sentiment")
            for idx, a in enumerate(rss_news[:8]):
                st.html(clean_html(render_rich_news_card(a, idx)))

# ──────────────────────────────────────────────────────────────────────────────
# TAB 6: VIRTUAL TRADE DESK
# ──────────────────────────────────────────────────────────────────────────────
elif current_tab == "TRADE_DESK":
    # Ticker Quote Batching
    held = list(st.session_state["portfolio_holdings"].keys())
    lp = get_live_prices_batch(held) if held else {}
    cash = st.session_state["portfolio_cash"]
    hmv = 0.0
    for tk, hi in st.session_state["portfolio_holdings"].items():
        sh = hi["shares"]
        cp = lp.get(tk, hi["avg_cost"]) or hi["avg_cost"]
        hmv += sh * cp

    pv = cash + hmv
    npl = pv - 100000.0
    npl_pct = (npl / 100000.0) * 100

    # Header Row
    h1, h2, h3 = st.columns(3)
    sign = "+" if npl >= 0 else ""
    color = "var(--rv-pos)" if npl >= 0 else "var(--rv-neg)"
    h1.markdown(f"""
    <div class="fintech-card" style="text-align:center;">
        <div class="metric-label">Net Portfolio Value</div>
        <div class="fin-readout">${pv:,.2f}</div>
        <div style="color:{color}; font-size:12px; font-weight:600;">{sign}${npl:,.2f} ({sign}{npl_pct:.2f}%)</div>
    </div>
    """, unsafe_allow_html=True)
    h2.markdown(f"""
    <div class="fintech-card" style="text-align:center;">
        <div class="metric-label">Buying Power</div>
        <div class="fin-readout" style="color:var(--rv-text);">${cash:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)
    h3.markdown(f"""
    <div class="fintech-card" style="text-align:center;">
        <div class="metric-label">Market Assets Value</div>
        <div class="fin-readout">${hmv:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)

    col_watch, col_chart, col_quote = st.columns([0.8, 2.2, 1.0])

    # 1. Left Watchlist Column
    with col_watch:
        st.subheader("Watchlists")
        watchlist_tickers = ["AAPL", "MSFT", "NVDA", "AMZN", "TSLA", "META", "GOOGL", "NFLX", "JPM", "LLY", "V", "DIS", "WMT", "UNH", "XOM"]
        with st.spinner("Syncing..."):
            wl_prices = get_live_prices_batch(watchlist_tickers)
            
        st.markdown("<div class='fintech-card' style='padding:0px !important;'>", unsafe_allow_html=True)
        st.markdown("""
        <table class="fintech-table" style="width:100%; border-collapse:collapse; font-size:12px; font-variant-numeric: tabular-nums;">
            <thead>
                <tr style="border-bottom:1px solid var(--rv-border); color:var(--rv-text-muted); font-size:11px; text-transform:uppercase; text-align:left;">
                    <th style="padding: 10px 12px; background-color: var(--rv-surface) !important;">Symbol</th>
                    <th style="padding: 10px 12px; text-align:right; background-color: var(--rv-surface) !important;">Last</th>
                    <th style="padding: 10px 12px; text-align:right; background-color: var(--rv-surface) !important;">Change</th>
                </tr>
            </thead>
            <tbody>
        """, unsafe_allow_html=True)
        for tk in watchlist_tickers:
            info = get_ticker_info(tk)
            chg = info.get("day_change_pct")
            price = wl_prices.get(tk) or info.get("previous_close")
            badge_style = ("background-color: var(--rv-pos-soft); color: var(--rv-pos); border: 1px solid var(--rv-pos); "
                           "padding: 3px 6px; border-radius: 4px; font-weight: 700; font-family: 'JetBrains Mono', monospace;"
                           ) if (chg or 0) >= 0 else (
                          "background-color: var(--rv-neg-soft); color: var(--rv-neg); border: 1px solid var(--rv-neg); "
                          "padding: 3px 6px; border-radius: 4px; font-weight: 700; font-family: 'JetBrains Mono', monospace;")
            if chg is None:
                badge_style = ("background-color: var(--rv-surface-hi); color: var(--rv-text-faint); "
                               "padding: 3px 6px; border-radius: 4px; font-weight: 600;")
            st.markdown(f"""
                <tr style="border-bottom: 1px solid var(--rv-border);">
                    <td style="padding: 10px 12px; font-weight:700;"><span class="rv-ticker-link" data-rv-ticker="{tk}" data-rv-dest="TRADE_DESK" role="button" tabindex="0" style="color:var(--rv-info); text-decoration:none;">{tk}</span></td>
                    <td style="padding: 10px 12px; text-align:right; font-weight:700; color:var(--rv-text); font-family:'JetBrains Mono', monospace;">{fmt_money(price)}</td>
                    <td style="padding: 10px 12px; text-align:right;"><span style="{badge_style}">{fmt_pct(chg)}</span></td>
                </tr>
            """, unsafe_allow_html=True)
        st.markdown("</tbody></table></div>", unsafe_allow_html=True)
        
        # ── Active Positions Grid ──
        st.subheader("Active Positions")
        holdings = st.session_state["portfolio_holdings"]
        if holdings:
            st.markdown("<div class='fintech-card' style='padding:0px !important;'>", unsafe_allow_html=True)
            st.markdown("""
            <table class="fintech-table" style="width:100%; border-collapse:collapse; font-size:11px; font-variant-numeric: tabular-nums;">
                <thead>
                    <tr style="border-bottom:1px solid var(--rv-border); color:var(--rv-text-muted); font-size:10px; text-transform:uppercase;">
                        <th style="padding: 8px 10px; text-align:left; background-color: var(--rv-surface) !important;">Sym</th>
                        <th style="padding: 8px 10px; text-align:right; background-color: var(--rv-surface) !important;">Shares</th>
                        <th style="padding: 8px 10px; text-align:right; background-color: var(--rv-surface) !important;">Value</th>
                        <th style="padding: 8px 10px; text-align:right; background-color: var(--rv-surface) !important;">Return</th>
                    </tr>
                </thead>
                <tbody>
            """, unsafe_allow_html=True)
            for h_tk, h_info in holdings.items():
                h_shares = h_info["shares"]
                h_cost = h_info["avg_cost"]
                h_curr = lp.get(h_tk, h_cost)
                h_val = h_shares * h_curr
                h_ret = ((h_curr - h_cost) / h_cost) * 100 if h_cost > 0 else 0.0
                h_sign = "+" if h_ret >= 0 else ""
                h_cc = "color-green" if h_ret >= 0 else "color-red"
                st.markdown(f"""
                    <tr style="border-bottom: 1px solid var(--rv-border);">
                        <td style="padding: 8px 10px; font-weight:700;"><span class="rv-ticker-link" data-rv-ticker="{h_tk}" data-rv-dest="TRADE_DESK" role="button" tabindex="0" style="color:var(--rv-info); text-decoration:none;">{h_tk}</span></td>
                        <td style="padding: 8px 10px; text-align:right; color:var(--rv-text); font-family:'JetBrains Mono', monospace;">{h_shares}</td>
                        <td style="padding: 8px 10px; text-align:right; color:var(--rv-text); font-weight:700; font-family:'JetBrains Mono', monospace;">${h_val:,.2f}</td>
                        <td style="padding: 8px 10px; text-align:right; font-weight:700;" class="{h_cc}">{h_sign}{h_ret:.1f}%</td>
                    </tr>
                """, unsafe_allow_html=True)
            st.markdown("</tbody></table></div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='fintech-card'><div style='color:var(--rv-text-muted); font-size:11px; text-align:center; padding: 12px 0;'>No active positions held.</div></div>", unsafe_allow_html=True)
            
        # ── Balance Summary ──
        st.subheader("Balance Summary")
        st.markdown(f"""
        <div class="fintech-card" style="padding: 12px; font-variant-numeric: tabular-nums;">
            <div style="display:flex; justify-content:space-between; margin-bottom: 8px; font-size:12px;">
                <span style="color:var(--rv-text-muted);">Cash Balance:</span>
                <span style="color:var(--rv-text); font-weight:700; font-family:'JetBrains Mono', monospace;">${cash:,.2f}</span>
            </div>
            <div style="display:flex; justify-content:space-between; margin-bottom: 8px; font-size:12px;">
                <span style="color:var(--rv-text-muted);">Assets Value:</span>
                <span style="color:var(--rv-text); font-weight:700; font-family:'JetBrains Mono', monospace;">${hmv:,.2f}</span>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:12px; border-top:1px solid var(--rv-border); padding-top:8px; margin-top:8px;">
                <span style="color:var(--rv-text-muted); font-weight:700;">Buying Power:</span>
                <span style="color:var(--rv-pos); font-weight:800; font-family:'JetBrains Mono', monospace;">${cash:,.2f}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 2. Center Chart & Order Entry Column
    ttk = st.session_state["active_ticker"]
    sp = get_live_price(ttk)
    
    with col_chart:
        st.subheader(f"Technical Charts: {ttk}")
        
        # Advanced technical chart indicators calculations
        df_prices = get_stock_data(ttk)["prices"]
        if not df_prices.empty and len(df_prices) >= 20:
            sma20_ser = df_prices["Close"].rolling(20).mean()
            sma60_ser = df_prices["Close"].rolling(60).mean()
            sma200_ser = df_prices["Close"].rolling(200).mean()
            
            macd_val, macd_sig, macd_hist = calculate_macd(df_prices["Close"])
            ema12 = calculate_ema(df_prices["Close"], 12)
            ema26 = calculate_ema(df_prices["Close"], 26)
            macd_line = ema12 - ema26
            macd_sig_line = calculate_ema(macd_line, 9)
            macd_hist_line = macd_line - macd_sig_line
            
            rsi_series = df_prices["Close"].copy()
            for idx in range(len(df_prices)):
                sub_ser = df_prices["Close"].iloc[:idx+1]
                rsi_series.iloc[idx] = calculate_rsi(sub_ser, 14)
                
            now = df_prices.index[-1]
            cutoff = now - timedelta(days=90)
            
            fig_advanced = make_advanced_chart(df_prices, cutoff, sma20_ser, sma60_ser, sma200_ser, rsi_series, macd_line, macd_sig_line, macd_hist_line)
            st.markdown("<div class='fintech-card' style='padding:6px !important;'>", unsafe_allow_html=True)
            st.plotly_chart(fig_advanced, use_container_width=True, config={"displayModeBar": True, "scrollZoom": True})
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='fintech-card'><div style='color:var(--rv-text-muted); font-size:12px;'>Insufficient stock history for advanced charts</div></div>", unsafe_allow_html=True)

        # Render custom React Order Entry component
        react_res = _REACT_ORDER_DESK(
            key="react_order_desk_inst",
            data={
                "active_ticker": ttk,
                "trade_order_type": st.session_state["trade_order_type"],
                "live_price": sp
            },
            height=360,
            on_active_ticker_change=lambda: None,
            on_trade_order_type_change=lambda: None,
            on_execute_trade_change=lambda: None
        )
        
        if react_res:
            if react_res.active_ticker is not None and react_res.active_ticker != st.session_state["active_ticker"]:
                st.session_state["active_ticker"] = react_res.active_ticker
                st.rerun()
            if react_res.trade_order_type is not None and react_res.trade_order_type != st.session_state["trade_order_type"]:
                st.session_state["trade_order_type"] = react_res.trade_order_type
                st.rerun()
                
            if react_res.execute_trade:
                order_info = react_res.execute_trade
                trade_ticker = order_info["ticker"].strip().upper()
                trade_type = order_info["type"]
                trade_qty = int(order_info["quantity"])
                trade_price = float(order_info["price"])
                trade_total = trade_price * trade_qty
                
                if trade_price > 0:
                    if trade_type == "BUY":
                        if trade_total > cash:
                            st.error("Insufficient Virtual Balance.")
                        else:
                            st.session_state["portfolio_cash"] = round(st.session_state["portfolio_cash"] - trade_total, 2)
                            h = st.session_state["portfolio_holdings"]
                            if trade_ticker in h:
                                os_h = h[trade_ticker]["shares"]
                                oc = h[trade_ticker]["avg_cost"]
                                ns = os_h + trade_qty
                                nc = ((os_h * oc) + trade_total) / ns
                                h[trade_ticker] = {"shares": ns, "avg_cost": round(nc, 2)}
                            else:
                                h[trade_ticker] = {"shares": trade_qty, "avg_cost": round(trade_price, 2)}
                            st.session_state["portfolio_history"].append({
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "ticker": trade_ticker,
                                "type": "BUY",
                                "shares": trade_qty,
                                "price": trade_price,
                                "total": trade_total
                            })
                            st.toast(f"Successfully bought {trade_qty} {trade_ticker} at ${trade_price:.2f}")
                            st.rerun()
                    else:
                        h = st.session_state["portfolio_holdings"]
                        if trade_ticker not in h or h[trade_ticker]["shares"] < trade_qty:
                            st.error("Inadequate Share Balance.")
                        else:
                            st.session_state["portfolio_cash"] = round(st.session_state["portfolio_cash"] + trade_total, 2)
                            h[trade_ticker]["shares"] -= trade_qty
                            if h[trade_ticker]["shares"] == 0:
                                del h[trade_ticker]
                            st.session_state["portfolio_history"].append({
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "ticker": trade_ticker,
                                "type": "SELL",
                                "shares": trade_qty,
                                "price": trade_price,
                                "total": trade_total
                            })
                            st.toast(f"Successfully sold {trade_qty} {trade_ticker} at ${trade_price:.2f}")
                            st.rerun()

    # 3. Right Quotes & L2 Book Column
    with col_quote:
        st.subheader("Quotes / Depth")
        
        info = get_ticker_info(ttk)
        chg = info.get("day_change_pct")
        cc = value_class(chg)
        
        st.markdown(f"""
        <div class="fintech-card" style="padding: 12px; margin-bottom: 6px;">
            <div style="font-size:11px; color:var(--rv-text-muted); font-weight:700; text-transform:uppercase;">Quote Details / {ttk}</div>
            <div style="font-size:24px; font-weight:800; color:var(--rv-text); margin-top:4px; font-variant-numeric: tabular-nums;">${sp:.2f}</div>
            <div class="{cc}" style="font-size:12px; font-weight:700; margin-top:2px;">{fmt_pct(chg)}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Order Book (L2) Mock Grid
        st.markdown("""
        <div class="fintech-card" style="padding: 10px; margin-bottom: 6px;">
            <div style="font-size:10px; color:var(--rv-text-muted); font-weight:700; text-transform:uppercase; margin-bottom:6px;">Order Book (L2)</div>
            <table style="width:100%; border-collapse:collapse; font-size:11px; font-variant-numeric: tabular-nums; font-family:'Inter', -apple-system, sans-serif;">
                <thead>
                    <tr style="border-bottom:1px solid var(--rv-border); color:var(--rv-text-muted);">
                        <th style="text-align:left; padding: 4px 0;">Bid Size</th>
                        <th style="text-align:center; padding: 4px 0;">Price</th>
                        <th style="text-align:right; padding: 4px 0;">Ask Size</th>
                    </tr>
                </thead>
                <tbody>
        """, unsafe_allow_html=True)
        for i in range(8):
            bp = sp - (0.05 * (i+1))
            ap = sp + (0.05 * (i+1))
            bs = int(100 * np.random.randint(1, 15))
            as_sz = int(100 * np.random.randint(1, 15))
            st.markdown(f"""
                    <tr style="border-bottom: 1px solid var(--rv-border);">
                        <td style="color:var(--rv-pos); font-weight:600; text-align:left; padding: 4px 0;">{bs}</td>
                        <td style="color:var(--rv-text); font-weight:600; text-align:center; padding: 4px 0;">${bp:.2f} | ${ap:.2f}</td>
                        <td style="color:var(--rv-neg); font-weight:600; text-align:right; padding: 4px 0;">{as_sz}</td>
                    </tr>
            """, unsafe_allow_html=True)
        st.markdown("""
                </tbody>
            </table>
        </div>
        """, unsafe_allow_html=True)

        # Time & Sales Mock prints
        st.markdown("""
        <div class="fintech-card" style="padding: 10px; margin-bottom: 6px;">
            <div style="font-size:10px; color:var(--rv-text-muted); font-weight:700; text-transform:uppercase; margin-bottom:6px;">Time & Sales</div>
            <table style="width:100%; border-collapse:collapse; font-size:11px; font-variant-numeric: tabular-nums; font-family:'Inter', -apple-system, sans-serif;">
                <thead>
                    <tr style="border-bottom:1px solid var(--rv-border); color:var(--rv-text-muted);">
                        <th style="text-align:left; padding: 4px 0;">Time</th>
                        <th style="text-align:right; padding: 4px 0;">Price</th>
                        <th style="text-align:right; padding: 4px 0;">Size</th>
                        <th style="text-align:right; padding: 4px 0;">Exch</th>
                    </tr>
                </thead>
                <tbody>
        """, unsafe_allow_html=True)
        for i in range(8):
            p_time = (datetime.now() - timedelta(seconds=i*3)).strftime("%H:%M:%S")
            p_price = sp + (0.01 * np.random.randn())
            p_sz = int(np.random.randint(10, 500))
            p_exch = np.random.choice(["ARCA", "NSDQ", "BATS", "NYSE"])
            cc_col = "color-green" if p_price >= sp else "color-red"
            st.markdown(f"""
                    <tr style="border-bottom: 1px solid var(--rv-border);">
                        <td style="color:var(--rv-text-muted); text-align:left; padding: 4px 0;">{p_time}</td>
                        <td class="{cc_col}" style="font-weight:600; text-align:right; padding: 4px 0;">${p_price:.2f}</td>
                        <td style="color:var(--rv-text); text-align:right; padding: 4px 0;">{p_sz}</td>
                        <td style="color:var(--rv-text-muted); text-align:right; padding: 4px 0;">{p_exch}</td>
                    </tr>
            """, unsafe_allow_html=True)
        st.markdown("""
                </tbody>
            </table>
        </div>
        """, unsafe_allow_html=True)

        # Asset Diversification Donut
        if not st.session_state["portfolio_holdings"]:
            labels, vals = ['Cash'], [cash]
        else:
            labels = ['Cash'] + list(st.session_state["portfolio_holdings"].keys())
            vals = [cash] + [st.session_state["portfolio_holdings"][t]["shares"] * lp.get(t, st.session_state["portfolio_holdings"][t]["avg_cost"]) for t in st.session_state["portfolio_holdings"]]
        
        fp = go.Figure(data=[go.Pie(labels=labels, values=vals, hole=.4, marker=dict(colors=[T.surface_alt, T.pos, T.info, T.neg, T.text_muted, T.text_faint]))])
        fp.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color=T.text_muted, family="'Inter', -apple-system, sans-serif", size=11),
            margin=dict(t=5, b=5, l=5, r=5),
            height=200,
            dragmode='pan'
        )
        st.markdown("<div class='fintech-card' style='padding:6px !important;'>", unsafe_allow_html=True)
        st.plotly_chart(fp, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
        # ── Order History Log ──
        st.subheader("Order History")
        history = st.session_state["portfolio_history"]
        if history:
            st.markdown("<div class='fintech-card' style='padding:0px !important;'>", unsafe_allow_html=True)
            st.markdown("""
            <table style="width:100%; border-collapse:collapse; font-size:11px; font-variant-numeric: tabular-nums;">
                <thead>
                    <tr style="border-bottom:1px solid var(--rv-border); color:var(--rv-text-muted); font-size:10px; text-transform:uppercase;">
                        <th style="padding: 6px 8px; text-align:left;">Time</th>
                        <th style="padding: 6px 8px; text-align:center;">Type</th>
                        <th style="padding: 6px 8px; text-align:left;">Sym</th>
                        <th style="padding: 6px 8px; text-align:right;">Total</th>
                    </tr>
                </thead>
                <tbody>
            """, unsafe_allow_html=True)
            # Show last 6 transactions
            for tx in reversed(history[-6:]):
                tx_time = tx["timestamp"].split(" ")[1] if " " in tx["timestamp"] else tx["timestamp"]
                tx_type = tx["type"]
                tx_cc = "color-green" if tx_type == "BUY" else "color-red"
                st.markdown(f"""
                    <tr style="border-bottom: 1px solid var(--rv-border);">
                        <td style="padding: 6px 8px; color:var(--rv-text-muted);">{tx_time}</td>
                        <td style="padding: 6px 8px; text-align:center; font-weight:700;" class="{tx_cc}">{tx_type}</td>
                        <td style="padding: 6px 8px; font-weight:700; color:var(--rv-text);">{tx['ticker']}</td>
                        <td style="padding: 6px 8px; text-align:right; color:var(--rv-text); font-weight:700;">${tx['total']:,.2f}</td>
                    </tr>
                """, unsafe_allow_html=True)
            st.markdown("</tbody></table></div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='fintech-card'><div style='color:var(--rv-text-muted); font-size:11px; text-align:center; padding: 12px 0;'>No orders executed yet.</div></div>", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# TAB 7: PATTERN GUIDE
# ──────────────────────────────────────────────────────────────────────────────
elif current_tab == "PATTERN_GUIDE":
    highlighted = st.session_state.get("highlighted_pattern", "")
    st.subheader("Chart Patterns Reference Guide")

    if highlighted:
        st.success(f"Focused pattern indicator: {highlighted}")
        if st.button("Reset Focus Highlights"):
            st.session_state["highlighted_pattern"] = ""
            st.rerun()

    tab1, tab2, tab3 = st.tabs(["Candlestick Anatomy", "Candlestick Formations", "Geometric Formations"])

    with tab1:
        st.subheader("Candlestick Basics")
        c1, c2, c3 = st.columns(3)
        c1.markdown("""
        <div class="fintech-card">
            <div style="font-size:13px; font-weight:600; color:var(--rv-pos); margin-bottom:6px;">BULLISH CANDLE</div>
            <p style="font-size:12px; color:var(--rv-text);">Stock closed higher than it opened.</p>
            <ul style="font-size:12px; color:var(--rv-text); padding-left: 14px;">
                <li><strong>Upper Wick:</strong> Highest price achieved</li>
                <li><strong>Body Top:</strong> Closing price</li>
                <li><strong>Body Bottom:</strong> Opening price</li>
                <li><strong>Lower Wick:</strong> Lowest price achieved</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        c2.markdown("""
        <div class="fintech-card">
            <div style="font-size:13px; font-weight:600; color:var(--rv-neg); margin-bottom:6px;">BEARISH CANDLE</div>
            <p style="font-size:12px; color:var(--rv-text);">Stock closed lower than it opened.</p>
            <ul style="font-size:12px; color:var(--rv-text); padding-left: 14px;">
                <li><strong>Upper Wick:</strong> Highest price achieved</li>
                <li><strong>Body Top:</strong> Opening price</li>
                <li><strong>Body Bottom:</strong> Closing price</li>
                <li><strong>Lower Wick:</strong> Lowest price achieved</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        dhl = "card-highlighted" if highlighted == "Doji" else ""
        c3.markdown(f"""
        <div class="fintech-card {dhl}">
            <div style="font-size:13px; font-weight:600; color:var(--rv-text-muted); margin-bottom:6px;">DOJI INDECISION</div>
            <p style="font-size:12px; color:var(--rv-text);">Open and close nearly identical. Signals market indecision.</p>
            <ul style="font-size:12px; color:var(--rv-text); padding-left: 14px;">
                <li><strong>Meaning:</strong> Standoff between bulls and bears.</li>
                <li><strong>Action:</strong> Wait for a breakouts or reversal candles.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        # Interactive Plotly Candlestick anatomy illustration
        fig_anatomy = go.Figure(data=[go.Candlestick(
            x=["Bullish Candle", "Bearish Candle", "Doji Indecision"],
            open=[100, 150, 120],
            high=[170, 180, 160],
            low=[80, 90, 80],
            close=[160, 100, 120.5],
            increasing=dict(line=dict(color=T.pos, width=3.5), fillcolor=T.pos),
            decreasing=dict(line=dict(color=T.neg, width=3.5), fillcolor=T.neg)
        )])
        fig_anatomy.update_layout(
            title=dict(text="Interactive Candlestick Schematics (Hover to inspect prices)", font=dict(size=12, color=T.text_muted)),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(t=35, b=10, l=10, r=10), height=320,
            xaxis=dict(showgrid=True, gridcolor=T.border, showline=True, linecolor=T.border_hi, rangeslider=dict(visible=False)),
            yaxis=dict(showgrid=True, gridcolor=T.border, showline=True, linecolor=T.border_hi, tickprefix="$")
        )
        st.markdown("<div class='fintech-card' style='padding:6px !important;'>", unsafe_allow_html=True)
        st.plotly_chart(fig_anatomy, use_container_width=True, config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        st.subheader("Common Candlestick Formations")
        m1, m2 = st.columns(2)
        with m1:
            st.markdown("##### Bullish Patterns")
            hhl = "card-highlighted" if highlighted == "Hammer" else ""
            st.markdown(f'<div class="fintech-card {hhl}"><div style="font-size:10px; color:var(--rv-pos); font-weight:700;">SINGLE CANDLE</div><div style="font-size:13px; font-weight:600; color:var(--rv-text); margin:2px 0;">Hammer</div><p style="font-size:12px; color:var(--rv-text);">Small body, long lower wick. Buyers surged back.</p><div style="font-size:10px; color:var(--rv-text-muted);">Wait for next candle above the high.</div></div>', unsafe_allow_html=True)
            ehl = "card-highlighted" if highlighted == "Bullish Engulfing" else ""
            st.markdown(f'<div class="fintech-card {ehl}"><div style="font-size:10px; color:var(--rv-pos); font-weight:700;">DOUBLE CANDLE</div><div style="font-size:13px; font-weight:600; color:var(--rv-text); margin:2px 0;">Bullish Engulfing</div><p style="font-size:12px; color:var(--rv-text);">Green candle engulfs prior red candle.</p><div style="font-size:10px; color:var(--rv-text-muted);">Look for high volume confirmation.</div></div>', unsafe_allow_html=True)
            dbhl = "card-highlighted" if highlighted == "Double Bottom" else ""
            st.markdown(f'<div class="fintech-card {dbhl}"><div style="font-size:10px; color:var(--rv-pos); font-weight:700;">MULTI-DAY</div><div style="font-size:13px; font-weight:600; color:var(--rv-text); margin:2px 0;">Double Bottom (W)</div><p style="font-size:12px; color:var(--rv-text);">Two bounces off support, forming W shape. Bullish reversal.</p><div style="font-size:10px; color:var(--rv-text-muted);">Buy when price breaks above the neckline.</div></div>', unsafe_allow_html=True)
            
            # W Pattern Plotly
            w_x = [1, 2, 3, 4, 5, 6, 7]
            w_y = [10, 5, 8, 4.8, 9, 7.5, 12]
            fig_w = go.Figure()
            fig_w.add_trace(go.Scatter(x=w_x, y=w_y, mode="lines+markers", line=dict(color=T.pos, width=3), name="Double Bottom (W)", showlegend=False))
            fig_w.add_shape(type="line", x0=1, y0=10, x1=7, y1=10, line=dict(color=T.text_muted, dash="dash"))
            fig_w.update_layout(
                title=dict(text="Double Bottom Schema (Neckline Breakout)", font=dict(size=11, color=T.text_muted)),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(t=30, b=10, l=10, r=10), height=180,
                xaxis=dict(visible=False), yaxis=dict(visible=False)
            )
            st.markdown("<div class='fintech-card' style='padding:4px !important; margin-top:8px;'>", unsafe_allow_html=True)
            st.plotly_chart(fig_w, use_container_width=True, config={"displayModeBar": False})
            st.markdown("</div>", unsafe_allow_html=True)

        with m2:
            st.markdown("##### Bearish Patterns")
            sshl = "card-highlighted" if highlighted == "Shooting Star" else ""
            st.markdown(f'<div class="fintech-card {sshl}"><div style="font-size:10px; color:var(--rv-neg); font-weight:700;">SINGLE CANDLE</div><div style="font-size:13px; font-weight:600; color:var(--rv-text); margin:2px 0;">Shooting Star</div><p style="font-size:12px; color:var(--rv-text);">Small body, long upper wick. Sellers surged back.</p><div style="font-size:10px; color:var(--rv-text-muted);">Wait for next candle below the low.</div></div>', unsafe_allow_html=True)
            behl = "card-highlighted" if highlighted == "Bearish Engulfing" else ""
            st.markdown(f'<div class="fintech-card {behl}"><div style="font-size:10px; color:var(--rv-neg); font-weight:700;">DOUBLE CANDLE</div><div style="font-size:13px; font-weight:600; color:var(--rv-text); margin:2px 0;">Bearish Engulfing</div><p style="font-size:12px; color:var(--rv-text);">Red candle engulfs prior green candle.</p><div style="font-size:10px; color:var(--rv-text-muted);">Check for high seller volume.</div></div>', unsafe_allow_html=True)
            dthl = "card-highlighted" if highlighted == "Double Top" else ""
            st.markdown(f'<div class="fintech-card {dthl}"><div style="font-size:10px; color:var(--rv-neg); font-weight:700;">MULTI-DAY</div><div style="font-size:13px; font-weight:600; color:var(--rv-text); margin:2px 0;">Double Top (M)</div><p style="font-size:12px; color:var(--rv-text);">Two failed peaks at resistance, forming M shape. Bearish reversal.</p><div style="font-size:10px; color:var(--rv-text-muted);">Sell when price breaks below the neckline.</div></div>', unsafe_allow_html=True)
            
            # M Pattern Plotly
            m_x = [1, 2, 3, 4, 5, 6, 7]
            m_y = [5, 10, 7, 10.2, 6.8, 5, 3]
            fig_m = go.Figure()
            fig_m.add_trace(go.Scatter(x=m_x, y=m_y, mode="lines+markers", line=dict(color=T.neg, width=3), name="Double Top (M)", showlegend=False))
            fig_m.add_shape(type="line", x0=1, y0=7, x1=7, y1=7, line=dict(color=T.text_muted, dash="dash"))
            fig_m.update_layout(
                title=dict(text="Double Top Schema (Neckline Breakdown)", font=dict(size=11, color=T.text_muted)),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(t=30, b=10, l=10, r=10), height=180,
                xaxis=dict(visible=False), yaxis=dict(visible=False)
            )
            st.markdown("<div class='fintech-card' style='padding:4px !important; margin-top:8px;'>", unsafe_allow_html=True)
            st.plotly_chart(fig_m, use_container_width=True, config={"displayModeBar": False})
            st.markdown("</div>", unsafe_allow_html=True)

    with tab3:
        st.subheader("Geometric Formations Table")
        st.markdown("""
        <div class="fintech-card">
            <table style="width:100%; border-collapse:collapse; font-size:13px;">
                <thead>
                    <tr style="border-bottom:1px solid var(--rv-border); color:var(--rv-text-muted); font-size:11px; text-transform:uppercase; text-align:left;">
                        <th style="padding-bottom:6px;">Type</th>
                        <th style="padding-bottom:6px;">Pattern</th>
                        <th style="padding-bottom:6px;">Description</th>
                        <th style="padding-bottom:6px;">Confirmation</th>
                    </tr>
                </thead>
                <tbody>
                    <tr style="border-bottom:1px solid var(--rv-border);">
                        <td style="padding:6px 0; color:var(--rv-pos); font-weight:600;">Bullish Continuation</td>
                        <td>Bullish Flag</td>
                        <td>Downward channel after sharp rise</td>
                        <td>Buy above top line</td>
                    </tr>
                    <tr style="border-bottom:1px solid var(--rv-border);">
                        <td style="padding:6px 0; color:var(--rv-pos); font-weight:600;">Bullish Continuation</td>
                        <td>Pennant</td>
                        <td>Triangle consolidation after rise</td>
                        <td>Buy above triangle</td>
                    </tr>
                    <tr style="border-bottom:1px solid var(--rv-border);">
                        <td style="padding:6px 0; color:var(--rv-pos); font-weight:600;">Bullish Reversal</td>
                        <td>Cup and Handle</td>
                        <td>U-bottom followed by small dip</td>
                        <td>Buy above handle top</td>
                    </tr>
                    <tr style="border-bottom:1px solid var(--rv-border);">
                        <td style="padding:6px 0; color:var(--rv-neg); font-weight:600;">Bearish Continuation</td>
                        <td>Bearish Flag</td>
                        <td>Upward channel after sharp fall</td>
                        <td>Sell below bottom line</td>
                    </tr>
                    <tr style="border-bottom:1px solid var(--rv-border);">
                        <td style="padding:6px 0; color:var(--rv-neg); font-weight:600;">Bearish Reversal</td>
                        <td>Double Top (M)</td>
                        <td>Two peaks at structural ceiling</td>
                        <td>Sell below neckline</td>
                    </tr>
                    <tr>
                        <td style="padding:6px 0; color:var(--rv-pos); font-weight:600;">Bullish Reversal</td>
                        <td>Double Bottom (W)</td>
                        <td>Two bounces off support floor</td>
                        <td>Buy above neckline</td>
                    </tr>
                </tbody>
            </table>
        </div>
        """, unsafe_allow_html=True)

    # ── GLOSSARY OF TERMS ──
    st.subheader("Technical Terms Glossary")
    st.markdown("""
<div class="fintech-card">
    <div style="font-size:14px; font-weight:600; color:var(--rv-text); margin-bottom:8px;">RSI (Relative Strength Index)</div>
    <p style="color:var(--rv-text); line-height:1.4; margin-bottom:12px;">Measures momentum on a 0-100 scale. Readings above 70 indicate an overbought state (potential pullback), while values below 30 suggest an oversold condition (potential bounce).</p>
    <div style="font-size:14px; font-weight:600; color:var(--rv-text); margin-bottom:8px;">SMA (Simple Moving Average)</div>
    <p style="color:var(--rv-text); line-height:1.4; margin-bottom:12px;">Smooths out price volatility by calculating average closing levels over specific intervals. The 20-day average tracks short-term momentum, the 60-day monitors medium-term trend, and the 200-day defines the structural long-term anchor.</p>
    <div style="font-size:14px; font-weight:600; color:var(--rv-text); margin-bottom:8px;">Volatility Cap Risk Calculator</div>
    <p style="color:var(--rv-text); line-height:1.4; margin-bottom:12px;">Applies position sizing logic capped at exactly 25% of total virtual equity. Formulated as: <strong>min(25%, TargetRisk / Volatility x 100)</strong>. This forces smaller position sizes on highly volatile assets to safeguard overall capital.</p>
    <div style="font-size:14px; font-weight:600; color:var(--rv-text); margin-bottom:8px;">Support & Resistance Floors</div>
    <p style="color:var(--rv-text); line-height:1.4; margin-bottom:12px;">Support marks the historical floor where buyers emerge to halt price declines. Resistance marks the historical ceiling where sellers supply stock to prevent further advances. Computed from the 20-day high and low parameters.</p>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# TAB: COPILOT — grounded chat over measured facts
# ──────────────────────────────────────────────────────────────────────────────
elif current_tab == "AI_COPILOT":
    _cp_symbol = st.session_state["active_ticker"]
    st.html(fx.section_header(
        "Copilot", f"grounded on measured data for {_cp_symbol}"))

    st.session_state.setdefault("copilot_messages", [])
    st.session_state.setdefault("copilot_facts_for", "")

    # Load a fact base for the active symbol. The copilot used to receive only
    # the ticker *string*, so a question about "SMA 20 vs SMA 60 and RSI" reached
    # the model with none of those numbers and it could only generalise. It now
    # answers over the same ledger the Workbench builds, and its numeric claims
    # are checked the same way.
    if st.session_state["copilot_facts_for"] != _cp_symbol:
        with st.spinner(f"Loading data for {_cp_symbol}…"):
            _ctx = wf.execute(
                wf.Workflow(
                    key="copilot_ctx", name="Copilot context", description="",
                    inputs=("symbol",),
                    steps=(
                        wf.Step("prices", "prices",
                                {"symbol": "$input.symbol", "period": "1y"},
                                label="Price history"),
                        wf.Step("indicators", "indicators",
                                {"symbol": "$input.symbol",
                                 "history": "$artifact:prices"},
                                depends_on=("prices",), label="Indicators"),
                        wf.Step("fundamentals", "fundamentals",
                                {"symbol": "$input.symbol"},
                                label="Fundamentals", required=False),
                        wf.Step("news", "news",
                                {"symbol": "$input.symbol", "limit": 8},
                                label="Headlines", required=False),
                    ),
                ),
                {"symbol": _cp_symbol},
            )
        st.session_state["copilot_run"] = _ctx
        st.session_state["copilot_facts_for"] = _cp_symbol
        st.session_state["copilot_messages"] = []

    _ctx_run = st.session_state.get("copilot_run")
    _ledger = _ctx_run.ledger if _ctx_run else None
    _headlines = []
    if _ctx_run and _ctx_run.results.get("news") and _ctx_run.results["news"].ok:
        _headlines = _ctx_run.results["news"].value.get("headlines", [])

    _model_label = wf_llm.active_model_label()
    _have_model = wf_llm.best_provider() is not None

    # Context strip: what the copilot can actually see.
    if _ctx_run and _ctx_run.status == "failed":
        st.html(
            '<div class="rv-card" style="border-color:var(--rv-neg)">'
            '<div class="rv-eyebrow" style="color:var(--rv-neg);margin-bottom:6px">'
            'No data for this symbol</div>'
            '<div style="font-size:var(--rv-fs-small);color:var(--rv-text-muted);'
            f'line-height:1.6">{_ctx_run.error}<br><br>The copilot will not answer '
            'questions about a symbol it could not measure.</div></div>')
    else:
        _c1, _c2, _c3, _c4 = st.columns(4)
        with _c1:
            st.html(fx.metric("Symbol", _cp_symbol))
        with _c2:
            st.html(fx.metric("Facts available", str(len(_ledger) if _ledger else 0)))
        with _c3:
            st.html(fx.metric("Headlines", str(len(_headlines))))
        with _c4:
            st.html(fx.metric("Model", _model_label.split(" · ")[-1]
                              if _have_model else "unavailable",
                              delta_kind="neutral" if _have_model else "neg"))

    if not _have_model:
        st.warning(
            "No language model is configured, so the copilot cannot answer. "
            "Set `FEATHERLESS_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, "
            "`DEEPSEEK_API_KEY` or `GEMINI_API_KEY`.",
            icon=":material/info:")

    # ── QUICK PROMPTS ──
    _quick = [
        ("Technical setup", "Describe the current technical setup."),
        ("Momentum", "What do the momentum indicators say right now?"),
        ("Valuation", "How does the valuation look on the measured figures?"),
        ("What's missing", "What would I need that this data does not include?"),
    ]
    _pending = None
    _qcols = st.columns(len(_quick))
    for _col, (_label, _prompt) in zip(_qcols, _quick):
        with _col:
            if st.button(_label, key=f"cp_quick_{_label}", width="stretch",
                         disabled=not _have_model):
                _pending = _prompt

    # ── TRANSCRIPT ──
    if not st.session_state["copilot_messages"]:
        st.html(fx.empty_state(
            f"Ask anything about {_cp_symbol}", "◈",
            "Answers are drawn from the measured facts below. Figures the "
            "copilot cannot back are flagged."))

    for _msg in st.session_state["copilot_messages"]:
        with st.chat_message(_msg["role"]):
            if _msg["role"] == "assistant" and _msg.get("verified_html"):
                st.html(_msg["verified_html"])
                if _msg.get("badge"):
                    st.html(_msg["badge"])
            else:
                st.markdown(_msg["content"])

    _typed = st.chat_input(f"Ask about {_cp_symbol}…", disabled=not _have_model)
    _question = _pending or _typed

    if _question and _have_model and _ledger is not None:
        st.session_state["copilot_messages"].append(
            {"role": "user", "content": _question})

        _system = (
            "You are a market research assistant. You are given a table of "
            "measured facts, each with an id like [f3].\n\n"
            "Rules:\n"
            "1. Every number you write MUST be immediately followed by the id "
            "of the fact it came from, e.g. \"trading at $182.40 [f1]\".\n"
            "2. Never state a number that is not in the fact table. If it was "
            "not measured, say so in words.\n"
            "3. Be concise. Describe what the data shows; do not give "
            "investment advice or price targets."
        )
        _history = "\n".join(
            f"{m['role']}: {m['content']}"
            for m in st.session_state["copilot_messages"][-6:-1]
        )
        _news_block = ("\n".join(f"- {h}" for h in _headlines[:8])
                       if _headlines else "(no headlines available)")
        _prompt = (
            f"Symbol: {_cp_symbol}\n\n"
            f"Measured facts:\n{_ledger.render_table()}\n\n"
            f"Recent headlines:\n{_news_block}\n\n"
            + (f"Earlier in this conversation:\n{_history}\n\n" if _history else "")
            + f"Question: {_question}"
        )

        with st.spinner(f"Thinking via {_model_label}…"):
            try:
                _answer = wf_llm.make_completer()(_prompt, _system)
            except Exception as _exc:      # noqa: BLE001
                _answer = None
                _err = str(_exc)

        if _answer:
            _report = wf.verify(_answer, _ledger)
            st.session_state["copilot_messages"].append({
                "role": "assistant",
                "content": _answer,
                "verified_html": wf_render.render_memo_html(
                    _answer, _ledger, _report),
                "badge": wf_render.render_verification_badge(_report),
            })
        else:
            # No canned answer. The copilot says the model failed.
            st.session_state["copilot_messages"].append({
                "role": "assistant",
                "content": f"The model could not be reached: {_err}",
            })
        st.rerun()

    # ── EVIDENCE ──
    # Collapsed. It is the backing detail, not the point - left expanded it
    # pushed the actual answer off screen behind thirty rows of table.
    if _ledger is not None and len(_ledger):
        with st.expander(f"What the copilot can see · {len(_ledger)} measurements"):
            st.caption(
                "Every figure in an answer above is drawn from this table and "
                "checked against it. Anything the copilot cannot back is marked "
                "unverified.")
            st.html(wf_render.render_evidence_html(_ledger, limit=60))


# ──────────────────────────────────────────────────────────────────────────────
# TAB: WORKBENCH — verifiable AI research workflows
# ──────────────────────────────────────────────────────────────────────────────
elif current_tab == "WORKBENCH":
    st.html(fx.section_header(
        "Workbench",
        "AI research where every figure is traceable to the call that measured it"))

    _wb_left, _wb_main = st.columns([1, 2.6], gap="medium")

    # ── CONTROLS ──
    with _wb_left:
        _templates = wf.list_templates()
        _keys = [t.key for t in _templates]
        _labels = {t.key: t.name for t in _templates}

        _chosen_key = st.selectbox(
            "Workflow", options=_keys, format_func=lambda k: _labels[k],
            key="wb_template")
        _template = wf.get_template(_chosen_key)
        st.caption(_template.description)

        _inputs = {}
        if "symbol" in _template.inputs:
            _inputs["symbol"] = st.text_input(
                "Symbol", value=st.session_state["active_ticker"],
                key="wb_symbol").strip().upper()
        if "thesis" in _template.inputs:
            _inputs["thesis"] = st.text_area(
                "Your thesis", key="wb_thesis", height=90,
                placeholder="e.g. NVDA's datacenter demand is durable through 2027")
        if "positions" in _template.inputs:
            _inputs["positions"] = {
                "cash": st.session_state["portfolio_cash"],
                "holdings": st.session_state["portfolio_holdings"],
            }
            _inputs["symbols"] = sorted(st.session_state["portfolio_holdings"]) or ["AAPL"]

        # Model availability is resolved before the run, not discovered at the
        # synthesis step, so the button can say what will actually happen.
        try:
            _providers = wf_llm.available_providers()
        except Exception:
            _providers = []

        if _providers:
            # Best available, chosen automatically - see workflow.llm.PREFERENCE.
            _provider_key = _providers[0].key
            st.html(fx.pulse_dot(wf_llm.active_model_label(), "pos"))
        else:
            _provider_key = None
            st.warning(
                "No language model configured. The workflow will still run and "
                "collect facts — it just won't write the memo. Set one of "
                "`FEATHERLESS_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, "
                "`DEEPSEEK_API_KEY` or `GEMINI_API_KEY`.",
                icon=":material/info:")

        _run_clicked = st.button("Run workflow", type="primary", width="stretch")

        if st.session_state.get("wb_run") is not None:
            if st.button("Clear", width="stretch"):
                st.session_state["wb_run"] = None
                st.rerun()

    # ── EXECUTE ──
    if _run_clicked:
        _missing = [k for k in _template.inputs
                    if k not in ("symbols",) and not _inputs.get(k)]
        if _missing:
            st.error(f"Missing input: {', '.join(_missing)}")
        else:
            _completer = None
            if _provider_key:
                try:
                    _completer = wf_llm.make_completer(_provider_key)
                except wf_llm.NoModelConfigured as exc:
                    st.warning(str(exc))

            with st.status("Running workflow…", expanded=True) as _status:
                def _report(kind, step_id, payload):
                    if kind == "step_started":
                        _status.write(f"▸ {step_id}")
                    elif kind == "step_ok":
                        _status.write(f"✓ {step_id} · {payload.duration_ms:.0f} ms")
                    elif kind == "step_failed":
                        _status.write(f"✗ {step_id} · {payload.error}")
                    elif kind == "step_skipped":
                        _status.write(f"– {step_id} skipped")
                    elif kind == "synthesis_started":
                        _status.write("▸ writing memo")

                _run = wf.execute(
                    _template, _inputs, llm=_completer,
                    model=(_provider_key or ""), on_event=_report)

                _status.update(
                    label=("Workflow complete" if _run.status == "ok"
                           else "Workflow halted"),
                    state=("complete" if _run.status == "ok" else "error"),
                    expanded=False)

            st.session_state["wb_run"] = _run

    # ── RESULTS ──
    _run = st.session_state.get("wb_run")

    with _wb_main:
        if _run is None:
            st.html(fx.empty_state(
                "No run yet", "◆",
                "Pick a workflow and run it. Every figure in the result will be "
                "traceable to the tool call that produced it."))
            st.html(wf_render.render_dag_html(_template, None))
        else:
            # Pipeline
            st.html(fx.section_header(
                "Pipeline",
                f"{_run.duration_ms:.0f} ms · {len(_run.ledger)} facts measured"))
            st.html(wf_render.render_dag_html(wf.get_template(_run.workflow_key), _run))

            # A halted run is the honest outcome, presented as such.
            if _run.status == "failed":
                st.html(
                    '<div class="rv-card" style="border-color:var(--rv-neg);'
                    'margin-top:var(--rv-space-3)">'
                    '<div class="rv-row" style="gap:9px;margin-bottom:8px">'
                    '<span class="rv-pulse" style="background:var(--rv-neg-fill)"></span>'
                    '<span style="font-size:var(--rv-fs-h3);font-weight:650;'
                    'color:var(--rv-text)">No memo was written</span></div>'
                    '<div style="font-size:var(--rv-fs-small);'
                    'color:var(--rv-text-muted);line-height:1.6">'
                    f'{_run.error}<br><br>A required step did not complete, so '
                    'the workflow stopped rather than letting the model write '
                    'around the gap. Any facts that were measured are listed '
                    'below and can still be inspected.</div></div>')

            elif _run.memo:
                _badge = wf_render.render_verification_badge(_run.verification)
                st.html(fx.section_header("Memo", note=""))
                st.html(
                    f'<div class="rv-card">'
                    f'<div class="rv-row rv-row--between" '
                    f'style="margin-bottom:var(--rv-space-3)">'
                    f'<span class="rv-eyebrow">Generated by '
                    f'{_run.model or "model"}</span>{_badge}</div>'
                    + wf_render.render_memo_html(
                        _run.memo, _run.ledger, _run.verification)
                    + "</div>")

                _flagged = _run.verification.flagged if _run.verification else []
                if _flagged:
                    _items = "".join(
                        f"<li><code>{c.text}</code> — {c.detail}</li>"
                        for c in _flagged)
                    st.html(
                        '<div class="rv-card" style="border-color:var(--rv-warn);'
                        'margin-top:var(--rv-space-2)">'
                        '<div class="rv-eyebrow" style="color:var(--rv-warn);'
                        'margin-bottom:6px">'
                        f'{len(_flagged)} figure(s) could not be verified</div>'
                        '<ul style="margin:0 0 0 18px;padding:0;'
                        'font-size:var(--rv-fs-small);color:var(--rv-text-muted);'
                        f'line-height:1.6">{_items}</ul></div>')
            else:
                st.html(
                    '<div class="rv-card" style="border-color:var(--rv-warn);'
                    'margin-top:var(--rv-space-3)">'
                    '<div class="rv-eyebrow" style="color:var(--rv-warn);'
                    'margin-bottom:6px">Facts collected, no memo</div>'
                    '<div style="font-size:var(--rv-fs-small);'
                    'color:var(--rv-text-muted);line-height:1.6">'
                    f'{_run.error or "No language model was configured."}</div></div>')

            # Evidence is always shown, whatever happened above.
            st.html(fx.section_header(
                "Evidence", f"{len(_run.ledger)} measurements"))
            st.html(wf_render.render_evidence_html(_run.ledger))

            with st.expander("Run record"):
                st.caption(
                    "The complete record: inputs, every tool call with its "
                    "timing and source, the fact ledger, and the verification "
                    "report. This is what makes a run reproducible.")
                st.json(_run.to_json(), expanded=False)


# ──────────────────────────────────────────────────────────────────────────────
# TAB 8: SECURITY CONSOLE
# ──────────────────────────────────────────────────────────────────────────────
elif current_tab == "SECURITY":
    st.html(fx.section_header(
        "Security", "Sign-in activity and the models that score it"))

    _events = auth_store.get_events(CURRENT_USER.username, limit=200)
    _session_risk = st.session_state.get(auth_ui.SESSION_RISK) or {}
    _cards = risk_scoring.model_cards()

    # ── CURRENT SESSION ──
    _sc1, _sc2, _sc3, _sc4 = st.columns(4)
    _band = _session_risk.get("band", "low")
    _band_token = {
        "low": ("var(--rv-pos)", "Low"),
        "elevated": ("var(--rv-warn)", "Elevated"),
        "high": ("var(--rv-neg)", "High"),
    }.get(_band, ("var(--rv-text-muted)", "Unknown"))

    with _sc1:
        st.html(f"""
        <div class="rv-metric">
          <span class="rv-metric-label">Session risk</span>
          <span class="rv-metric-value" style="color:{_band_token[0]}">
            {int(_session_risk.get('score', 0) * 100)}%</span>
          <span class="rv-metric-delta" style="color:{_band_token[0]}">
            {_band_token[1]}</span>
        </div>""")
    with _sc2:
        st.html(fx.metric("Signed in from",
                          _session_risk.get("location") or "Unknown location"))
    with _sc3:
        st.html(fx.metric("Known devices", str(len(CURRENT_USER.known_devices))))
    with _sc4:
        _fails = auth_store.count_recent_failures(CURRENT_USER.username, 86400)
        st.html(fx.metric(
            "Failed attempts (24h)", str(_fails),
            delta="Review activity below" if _fails else "None",
            delta_kind="neg" if _fails else "neutral"))

    if _session_risk.get("reasons"):
        st.html(
            '<div class="rv-card" style="margin-top:var(--rv-space-2)">'
            '<div class="rv-eyebrow" style="margin-bottom:6px">'
            'Why this session was scored the way it was</div>'
            '<ul style="margin:0 0 0 18px;padding:0;font-size:var(--rv-fs-small);'
            'color:var(--rv-text-muted);line-height:1.6">'
            + "".join(f"<li>{r}</li>" for r in _session_risk["reasons"])
            + "</ul></div>"
        )

    # ── ACTIVITY ──
    st.html(fx.section_header("Recent activity", f"{len(_events)} events"))

    if not _events:
        st.html(fx.empty_state("No sign-in activity recorded yet", "◇"))
    else:
        _rows = []
        for _e in _events[:40]:
            _when = datetime.fromtimestamp(_e["timestamp"]).strftime("%d %b  %H:%M")
            _place = ", ".join(p for p in (_e.get("city"), _e.get("country_code")) if p) \
                or "Unknown"
            _decision = _e.get("decision", "")
            _pill = {
                "allow": ("pill-pos", "Allowed"),
                "challenge": ("pill-neut", "Challenged"),
                "challenge_passed": ("pill-pos", "Verified"),
                "deny": ("pill-neg", "Blocked"),
            }.get(_decision, ("pill-neut", _decision or "—"))
            _risk_pct = int(_e.get("risk_score", 0) * 100)
            _bot_pct = int(_e.get("bot_score", 0) * 100)
            _flags = " ".join(
                f'<span class="pill-neut">{f}</span>'
                for f in (["datacenter"] if _e.get("is_hosting") else [])
                + (["proxy"] if _e.get("is_proxy") else [])
                + list(_e.get("hard_rules") or [])
            )
            _rows.append(f"""
            <tr>
              <td class="rv-mono">{_when}</td>
              <td><span class="{_pill[0]}">{_pill[1]}</span></td>
              <td class="rv-right">{_risk_pct}%</td>
              <td class="rv-right">{_bot_pct}%</td>
              <td>{_place}</td>
              <td class="rv-truncate" style="max-width:150px">{_e.get('org') or _e.get('asn') or '—'}</td>
              <td>{_flags or '—'}</td>
            </tr>""")

        st.html(
            '<div class="rv-card rv-card--flush" style="overflow-x:auto">'
            '<table><thead><tr>'
            '<th>When</th><th>Outcome</th>'
            '<th class="rv-right">Risk</th><th class="rv-right">Bot</th>'
            '<th>Location</th><th>Network</th><th>Flags</th>'
            '</tr></thead><tbody>' + "".join(_rows) + "</tbody></table></div>"
        )

    # ── MODELS ──
    st.html(fx.section_header(
        "Detection models", "Trained on simulated data - see caveat"))

    _mc1, _mc2 = st.columns(2)
    for _col, (_key, _title) in zip(
        (_mc1, _mc2),
        (("login_risk", "Suspicious sign-in"), ("bot_detector", "Automation")),
    ):
        _card = _cards.get(_key) or {}
        with _col:
            if not _card:
                st.html(fx.empty_state(
                    f"{_title} model not trained", "◇",
                    "Run: python -m auth.train"))
                continue
            _op = _card.get("operating_point", {})
            _top = _card.get("feature_importance", [])[:5]
            _bars = "".join(
                f'<div class="rv-row" style="gap:8px;margin-bottom:3px">'
                f'<span style="font-size:var(--rv-fs-micro);'
                f'color:var(--rv-text-muted);width:150px;flex:none" '
                f'class="rv-truncate">{_f["feature"]}</span>'
                f'<span style="flex:1;height:5px;background:var(--rv-surface-hi);'
                f'border-radius:999px;overflow:hidden">'
                f'<span style="display:block;height:100%;'
                f'width:{min(100, _f["importance"] / max(_top[0]["importance"], 1e-9) * 100):.0f}%;'
                f'background:var(--rv-accent-fill)"></span></span></div>'
                for _f in _top
            )
            st.html(f"""
            <div class="rv-card rv-spotlight">
              <div class="rv-row rv-row--between" style="margin-bottom:10px">
                <span style="font-size:var(--rv-fs-h3);font-weight:650;
                      color:var(--rv-text)">{_title}</span>
                <span class="pill-neut">{_card.get('n_test', 0)} held-out</span>
              </div>
              <div class="rv-grid" style="grid-template-columns:repeat(4,1fr);
                   margin-bottom:12px">
                <div><div class="rv-metric-label">ROC-AUC</div>
                  <div class="rv-num" style="font-weight:600">{_card.get('roc_auc', 0):.3f}</div></div>
                <div><div class="rv-metric-label">Precision</div>
                  <div class="rv-num" style="font-weight:600">{_op.get('precision', 0):.3f}</div></div>
                <div><div class="rv-metric-label">Recall</div>
                  <div class="rv-num" style="font-weight:600">{_op.get('recall', 0):.3f}</div></div>
                <div><div class="rv-metric-label">FPR</div>
                  <div class="rv-num" style="font-weight:600">{_op.get('false_positive_rate', 0):.3f}</div></div>
              </div>
              <div class="rv-eyebrow" style="margin-bottom:6px">
                Top features by permutation importance</div>
              {_bars}
            </div>
            """)

    st.html(
        '<div class="rv-card" style="border-color:var(--rv-warn);'
        'margin-top:var(--rv-space-2)">'
        '<div class="rv-eyebrow" style="color:var(--rv-warn);margin-bottom:6px">'
        'Read before trusting these numbers</div>'
        '<div style="font-size:var(--rv-fs-small);color:var(--rv-text-muted);'
        'line-height:1.6">Both models are trained on <strong>simulated</strong> '
        'sign-ins, because no labelled corpus of real attempts exists for this '
        'application. The scores above measure how well each model recovers its '
        'own generator, not how it would perform against a live adversary. '
        'Every real sign-in is logged in the schema the generator emits, so the '
        'models can be retrained on genuine data once enough has accumulated: '
        '<code>python -m auth.train</code>.</div></div>'
    )


# ==============================================================================
# SIDEBAR — compact black AI helper
# ==============================================================================


def _render_side_chat_html(messages):
    """Compact custom chat bubbles — logo avatars, no Streamlit smart_toy text."""
    import html as _html
    import re as _re

    bubbles = []
    for msg in messages[-12:]:
        role = msg.get("role", "assistant")
        raw = str(msg.get("content", ""))
        parts = []
        last = 0
        for m in _re.finditer(r"\*\*(.+?)\*\*", raw):
            parts.append(_html.escape(raw[last:m.start()]))
            parts.append(f"<strong>{_html.escape(m.group(1))}</strong>")
            last = m.end()
        parts.append(_html.escape(raw[last:]))
        body = "".join(parts).replace("\n", "<br>")
        cls = "ai-bubble user" if role == "user" else "ai-bubble bot"
        bubbles.append(f'<div class="{cls}">{body}</div>')
    return '<div class="ai-chat-scroll">' + "".join(bubbles) + "</div>"


with st.sidebar:
    # The ticker the sidebar copilot is reasoning about. This comes from
    # Raaghav's branch and is the correct fix for a long-standing bug: the
    # sidebar previously read st.session_state["selected_ticker"], a key that
    # was never written anywhere in the app, so the copilot always believed the
    # user was looking at AAPL regardless of what was on screen.
    context_ticker = (st.session_state.get("active_ticker") or "AAPL").strip().upper()

    # Sidebar mark, from Raaghav's branch. Recoloured onto theme tokens so it
    # follows the active palette instead of pinning two hardcoded hexes.
    _side_logo = (
        '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M4 16.5L9.2 11.2L12.8 14.8L20 7.5" stroke="var(--rv-accent-fill)" '
        'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M15.5 7.5H20V12" stroke="var(--rv-info)" stroke-width="2.2" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )

    # ── APPEARANCE ──
    # Every control here maps to one token in theme.py. Changing any of them
    # rebuilds the stylesheet on the next rerun; nothing needs a page reload.
    with st.expander("Appearance", expanded=False):
        # Each control seeds itself from the canonical dict and writes back
        # through on_change, so a widget whose state Streamlit collected on a
        # run where the sidebar did not render is rebuilt from the saved value
        # rather than from the default.
        def _select(label, name, options, labeller, **kw):
            st.selectbox(
                label, options=options, format_func=labeller,
                index=options.index(pref(name)) if pref(name) in options else 0,
                key=f"ui_{name}", on_change=_commit_pref, args=(name,), **kw
            )

        _pal_col, _acc_col = st.columns(2)
        with _pal_col:
            _select("Palette", "palette", list(theme_mod.PALETTES),
                    lambda k: theme_mod.PALETTES[k].label)
        with _acc_col:
            _select("Accent", "accent", list(theme_mod.ACCENTS),
                    lambda k: theme_mod.ACCENTS[k][0])

        _den_col, _rad_col = st.columns(2)
        with _den_col:
            _select("Density", "density", list(theme_mod.DENSITIES),
                    lambda k: theme_mod.DENSITIES[k].label,
                    help="Spacing, control heights and table row heights.")
        with _rad_col:
            _select("Corners", "radius", list(theme_mod.RADII),
                    lambda k: theme_mod.RADII[k][0])

        _select("Motion", "motion", list(theme_mod.MOTION),
                lambda k: theme_mod.MOTION[k][0],
                help="Scales every animation in the app. Your operating "
                     "system's reduce-motion setting overrides this regardless.")

        _select("Gain / loss colours", "cvd", list(theme_mod.CVD_PAIRS),
                lambda k: theme_mod.CVD_PAIRS[k][0],
                help="Red/green is the hardest pair to distinguish with the "
                     "most common form of colour blindness, and it carries the "
                     "most important signal in the product.")

        st.slider("Text size", min_value=0.85, max_value=1.3, step=0.05,
                  value=float(pref("type_scale")),
                  key="ui_type_scale", on_change=_commit_pref, args=("type_scale",))

        _t1, _t2 = st.columns(2)
        with _t1:
            st.toggle("Glass", value=bool(pref("glass")), key="ui_glass",
                      on_change=_commit_pref, args=("glass",),
                      help="Translucent card surfaces.")
            st.toggle("Grid lines", value=bool(pref("grid_lines")),
                      key="ui_grid_lines", on_change=_commit_pref,
                      args=("grid_lines",))
        with _t2:
            st.toggle("Effects", value=bool(pref("effects")), key="ui_effects",
                      on_change=_commit_pref, args=("effects",),
                      help="Cursor spotlight, click sparks, counters.")
            st.toggle("Small caps", value=bool(pref("uppercase_labels")),
                      key="ui_uppercase_labels", on_change=_commit_pref,
                      args=("uppercase_labels",))

        _save_col, _reset_col = st.columns(2)
        with _save_col:
            if st.button("Save", width="stretch",
                         help="Store these settings on your account."):
                _prefs = dict(CURRENT_USER.preferences or {})
                _prefs["appearance"] = dict(st.session_state["appearance"])
                auth_store.update_user(CURRENT_USER.username, preferences=_prefs)
                st.success("Saved.", icon=":material/check:")
        with _reset_col:
            if st.button("Reset", width="stretch"):
                st.session_state["appearance"] = dict(APPEARANCE_DEFAULTS)
                for _n in APPEARANCE_DEFAULTS:
                    st.session_state.pop(f"ui_{_n}", None)
                st.rerun()

    st.markdown("### 💬 AI Copilot Assistant")
    st.caption("Chat with an institutional AI market assistant powered by Featherless AI:")
    
    # No model picker. "Which model" is not a decision a person opening a
    # market terminal has the information to make, and a dropdown of names
    # invites picking a weaker one by accident. The app takes the best provider
    # it has a key for (workflow.llm.PREFERENCE) and says which that is.
    selected_copilot_model = wf_llm.active_model_label()
    st.caption(f"Model: {selected_copilot_model}")
    st.markdown(
        f"""
        <div class="ai-side-shell">
            <div class="ai-side-head">
                <div class="ai-side-logo">{_side_logo}</div>
                <div>
                    <div class="ai-side-title">Reverie AI</div>
                    <div class="ai-side-sub">Market desk helper</div>
                </div>
                <div class="ai-side-status"><i></i>LIVE</div>
            </div>
            <div class="ai-side-chiprow">
                <span class="ai-side-chip">Trend</span>
                <span class="ai-side-chip">Risk</span>
                <span class="ai-side-chip">Levels</span>
            </div>
            <div class="ai-side-ticker">
                <span>Focus</span>
                <strong>{context_ticker}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "sidebar_chat_messages" not in st.session_state:
        st.session_state["sidebar_chat_messages"] = [
            {
                "role": "assistant",
                "content": (
                    f"Ready on **{context_ticker}**. Ask about trend, momentum, "
                    "risk framing, or key levels."
                ),
            }
        ]

    st.markdown('<div class="ai-clear-wrap">', unsafe_allow_html=True)
    clear_ai = st.button("Clear chat", use_container_width=True, key="sidebar_clear_chat")
    st.markdown("</div>", unsafe_allow_html=True)
    if clear_ai:
        st.session_state["sidebar_chat_messages"] = [
            {
                "role": "assistant",
                "content": f"Cleared. Still focused on **{context_ticker}**.",
            }
        ]
        st.rerun()

    st.markdown(
        _render_side_chat_html(st.session_state["sidebar_chat_messages"]),
        unsafe_allow_html=True,
    )

    user_input = st.chat_input(f"Ask about {context_ticker}…")
    if user_input:
        st.session_state["sidebar_chat_messages"].append({"role": "user", "content": user_input})
        # Routed through workflow.llm rather than chat_with_ai_copilot, whose
        # final fallback returns a canned "Market Copilot Note: Ticker X is
        # currently consolidating..." styled exactly like a real answer. A user
        # with a dead key could not tell. This path says the model failed.
        _side_ledger = None
        _side_run = st.session_state.get("copilot_run")
        if _side_run is not None and st.session_state.get("copilot_facts_for") == context_ticker:
            _side_ledger = _side_run.ledger

        _side_system = (
            "You are a market desk assistant. Be concise and describe only what "
            "the data shows. Do not give investment advice or price targets."
        )
        if _side_ledger is not None and len(_side_ledger):
            _side_system += (
                "\n\nEvery number you write MUST be followed by the id of the "
                "fact it came from, e.g. [f3]. Never state a number that is not "
                "in the fact table."
            )
            _side_prompt = (
                f"Symbol: {context_ticker}\n\nMeasured facts:\n"
                f"{_side_ledger.render_table()}\n\nQuestion: {user_input}"
            )
        else:
            _side_system += (
                "\n\nYou have no measured data for this symbol. Say so rather "
                "than estimating any figure."
            )
            _side_prompt = f"Symbol: {context_ticker}\n\nQuestion: {user_input}"

        with st.spinner("Thinking…"):
            try:
                reply = wf_llm.make_completer()(_side_prompt, _side_system)
            except Exception as _side_exc:      # noqa: BLE001
                reply = f"The model is unavailable right now: {_side_exc}"
        st.session_state["sidebar_chat_messages"].append(
            {"role": "assistant", "content": reply}
        )
        st.rerun()
