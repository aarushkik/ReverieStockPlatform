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

# Import backend engine
from data_fetcher import get_stock_data
from analyzer import run_analysis, analyze_sentiment
from agent_logic import evaluate_ticker
from dashboard import generate_markdown_report

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
                    <div style="background-color: #11151F; border: 1px solid #1E2433; border-radius: 8px; padding: 20px; font-family: 'Inter', -apple-system, sans-serif; color: #FFFFFF;">
                        <h2 style="font-size: 13px; font-weight: 800; color: #8A94A6; text-transform: uppercase; letter-spacing: 0.8px; margin-top: 0; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid #1E2433;">Simulation Order Desk</h2>
                        
                        <!-- Ticker Symbol -->
                        <div style="margin-bottom: 16px;">
                            <label style="display: block; font-size: 11px; font-weight: 700; color: #8A94A6; text-transform: uppercase; margin-bottom: 6px;">Ticker Symbol</label>
                            <input 
                                type="text" 
                                value=${ticker} 
                                onChange=${(e) => handleTickerChange(e.target.value)}
                                style="width: 100%; box-sizing: border-box; background-color: #161B26; border: 1px solid #1E2433; color: #FFFFFF; font-size: 14px; border-radius: 4px; padding: 10px; outline: none; font-weight: 700; text-transform: uppercase; transition: border-color 0.2s;"
                                onFocus=${(e) => e.target.style.borderColor = '#00E676'}
                                onBlur=${(e) => e.target.style.borderColor = '#1E2433'}
                            />
                        </div>
                        
                        <!-- BUY/SELL Toggles -->
                        <div style="margin-bottom: 16px;">
                            <label style="display: block; font-size: 11px; font-weight: 700; color: #8A94A6; text-transform: uppercase; margin-bottom: 6px;">Transaction Type</label>
                            <div style=${{
                                display: "grid",
                                gridTemplateColumns: "1fr 1fr",
                                gap: "8px",
                                backgroundColor: "#161B26",
                                padding: "4px",
                                borderRadius: "4px",
                                border: "1px solid " + (orderType === "BUY" ? "#00E676" : "#FF1744")
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
                                        backgroundColor: orderType === "BUY" ? "#00E676" : "transparent",
                                        color: orderType === "BUY" ? "#0B0E14" : "#8A94A6",
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
                                        backgroundColor: orderType === "SELL" ? "#FF1744" : "transparent",
                                        color: orderType === "SELL" ? "#FFFFFF" : "#8A94A6",
                                        boxShadow: orderType === "SELL" ? "0 0 14px rgba(255, 23, 68, 0.4)" : "none"
                                    }}
                                >
                                    SELL
                                </button>
                            </div>
                        </div>
                        
                        <!-- Share Count -->
                        <div style="margin-bottom: 16px;">
                            <label style="display: block; font-size: 11px; font-weight: 700; color: #8A94A6; text-transform: uppercase; margin-bottom: 6px;">Share Count</label>
                            <input 
                                type="number" 
                                min="1" 
                                value=${qty} 
                                onChange=${(e) => setQty(Math.max(1, parseInt(e.target.value) || 1))}
                                style="width: 100%; box-sizing: border-box; background-color: #161B26; border: 1px solid #1E2433; color: #FFFFFF; font-size: 14px; border-radius: 4px; padding: 10px; outline: none; font-weight: 700;"
                            />
                        </div>
                        
                        <!-- Unit Price & Est Total -->
                        <div style="background-color: #161B26; border: 1px solid #1E2433; border-radius: 4px; padding: 12px; font-size: 12px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                            <div>
                                <span style="color: #8A94A6;">Unit Price:</span>
                                <strong style="color: #FFFFFF; margin-left: 6px; font-family: 'JetBrains Mono', monospace; font-size: 13px;">$${sp.toFixed(2)}</strong>
                            </div>
                            <div>
                                <span style="color: #8A94A6;">Est Total:</span>
                                <strong style=${{
                                    color: orderType === 'BUY' ? '#00E676' : '#FF1744',
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
                                backgroundColor: sp === 0 ? "#1E2433" : (orderType === "BUY" ? "#00E676" : "#FF1744"),
                                color: sp === 0 ? "#8A94A6" : (orderType === "BUY" ? "#0B0E14" : "#FFFFFF"),
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
st.set_page_config(
    page_title="QUANTVIZ TERMINAL",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==============================================================================
# CSS & TYPOGRAPHY SYSTEM
# ==============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700;800&display=swap');
    
    /* Fade-in glide-up transitions for screen switches */
    @keyframes fadeInSlideUp {
        from {
            opacity: 0;
            transform: translateY(12px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    .fintech-card, .stPlotlyChart, div[data-testid="stVerticalBlockBorderContainer"] {
        animation: fadeInSlideUp 0.45s cubic-bezier(0.16, 1, 0.3, 1) both;
    }

    /* 1. Global Viewport Reset & Spatial Compression */
    .block-container {
        max-width: 99% !important;
        padding-top: 5rem !important;
        padding-bottom: 0.5rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        background-color: #0B0E14 !important;
    }
    header, footer, [data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stSidebarCollapseButton"] {
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
    }
    .element-container, .stVerticalBlock, [data-testid="stVerticalBlock"] {
        gap: 0.05rem !important;
        margin: 0px !important;
        padding: 0px !important;
    }
    div[data-testid="stHorizontalBlock"] {
        gap: 0.15rem !important;
        margin: 0px !important;
        padding: 0px !important;
        display: flex !important;
        align-items: stretch !important;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 6px !important; }
    .stTabs [data-baseweb="tab"] {
        background-color: #121620 !important;
        color: #8A94A6 !important;
        border-radius: 4px 4px 0px 0px !important;
        padding: 8px 16px !important;
        font-size: 13px !important;
        font-weight: 800 !important;
        text-transform: uppercase !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
        transition: all 0.2s ease;
    }
    .stTabs [aria-selected="true"] {
        color: #00E676 !important;
        border-bottom-color: #00E676 !important;
        text-shadow: 0 0 10px rgba(0,230,118,0.3);
    }

    /* 2. Typography Standard */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, sans-serif !important;
    }
    .stApp {
        background-color: #0B0E14 !important;
        color: #FFFFFF !important;
    }
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Inter', -apple-system, sans-serif !important;
        text-transform: uppercase !important;
        letter-spacing: 0.8px;
    }
    h1 {
        font-size: 18px !important;
        font-weight: 900 !important;
        color: #FFFFFF !important;
        margin-bottom: 8px !important;
        margin-top: 0px !important;
    }
    h2, h3, h4, h5, h6 {
        font-size: 15px !important;
        font-weight: 900 !important;
        color: #FFFFFF !important;
        margin-top: 10px !important;
        margin-bottom: 10px !important;
        padding-bottom: 4px !important;
        border-bottom: 1px solid #1E2433 !important;
        border-left: 3px solid #00E676 !important;
        padding-left: 8px !important;
    }
    p, li, span, div, td, th {
        font-size: 14px !important;
        font-weight: 600 !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
    }

    /* 3. Premium Card Framework */
    .fintech-card {
        background-color: #11151F !important;
        border: 1px solid #1E2433 !important;
        border-radius: 6px !important;
        padding: 14px !important;
        margin-bottom: 8px !important;
        display: flex;
        flex-direction: column;
        width: 100%;
        height: 100%;
        box-sizing: border-box;
        overflow: hidden;
    }
    .card-highlighted {
        border: 1px solid #00C805 !important;
    }
    
    /* Native Container Overrides */
    div[data-testid="stVerticalBlockBorderContainer"] {
        background-color: #11151F !important;
        border: 1px solid #1E2433 !important;
        border-radius: 4px !important;
        padding: 12px !important;
        margin-bottom: 6px !important;
    }
    
    /* Sleek Zero-Border Financial Matrix Tables */
    table, th, td, tr {
        border: none !important;
        border-collapse: collapse !important;
        background-color: transparent !important;
    }
    th {
        color: #8A94A6 !important;
        font-size: 12px !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        text-align: left !important;
        padding: 4px 12px !important;
        border-bottom: 1px solid #1E2433 !important;
    }
    td {
        padding: 6px 12px !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        color: #FFFFFF !important;
        line-height: 1.2 !important;
        border-bottom: 1px solid #1E2433 !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    .metric-box {
        background-color: #161B26 !important;
        border: 1px solid #1E2433 !important;
        border-radius: 4px !important;
        padding: 8px !important;
        text-align: center;
    }
    .metric-label {
        font-size: 12px !important;
        color: #8A94A6 !important;
        text-transform: uppercase;
        margin-bottom: 4px;
        font-weight: 600;
    }
    .metric-val {
        font-size: 16px !important;
        font-weight: 700 !important;
        color: #FFFFFF !important;
        font-family: 'JetBrains Mono', monospace !important;
    }
    .fin-readout {
        font-size: 22px !important;
        font-weight: 700 !important;
        color: #FFFFFF !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* 4. Form Control Overhaul */
    div[data-baseweb="input"], div[data-baseweb="textarea"], div[data-baseweb="select"] > div {
        background-color: #161B26 !important;
        border-radius: 4px !important;
        border: 1px solid #1E2433 !important;
        color: #FFFFFF !important;
    }
    div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea {
        color: #FFFFFF !important;
        font-size: 13px !important;
    }
    div[data-baseweb="input"]:focus-within, div[data-baseweb="select"] > div:focus-within {
        border-color: #1E2433 !important;
        box-shadow: none !important;
    }
    .stTextInput input, .stNumberInput input, .stSelectbox [role="combobox"] {
        background-color: #161B26 !important;
        border: 1px solid #1E2433 !important;
        color: #FFFFFF !important;
        border-radius: 4px !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus, .stSelectbox [role="combobox"]:focus {
        border-color: #1E2433 !important;
        box-shadow: none !important;
    }
    .stNumberInput button {
        background-color: #161B26 !important;
        color: #8A94A6 !important;
        border: 1px solid #1E2433 !important;
    }

    /* 5. Flat Segmented Toggles & Action Buttons */
    .segmented-toggles {
        border-radius: 4px !important;
        padding: 4px !important;
        background-color: #161B26 !important;
        transition: border-color 0.2s ease-in-out;
    }
    .segmented-toggles.buy-active {
        border: 1px solid #00C805 !important;
    }
    .segmented-toggles.sell-active {
        border: 1px solid #FF3B30 !important;
    }
    .seg-buy-on button {
        background-color: #00C805 !important;
        color: #0B0E14 !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 4px !important;
    }
    .seg-sell-on button {
        background-color: #FF3B30 !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 4px !important;
    }
    .seg-off button {
        background-color: #161B26 !important;
        color: #8A94A6 !important;
        border: 1px solid #1E2433 !important;
        border-radius: 4px !important;
    }
    .exec-btn button {
        background-color: #00C805 !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
        padding: 10px 0 !important;
        border-radius: 4px !important;
        border: none !important;
        margin: 0px !important;
        width: 100% !important;
        font-size: 13px !important;
        box-shadow: 0 4px 15px rgba(0, 200, 5, 0.3);
        transition: all 0.2s ease;
    }
    .exec-btn button:hover {
        background-color: #00e606 !important;
        box-shadow: 0 6px 20px rgba(0, 200, 5, 0.4);
    }
    div.stButton > button, div.stDownloadButton > button {
        background-color: #161B26 !important;
        color: #FFFFFF !important;
        border: 1px solid #1E2433 !important;
        border-radius: 4px !important;
        font-size: 13px !important;
        font-weight: 700 !important;
        padding: 8px 16px !important;
        transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1) !important;
        position: relative !important;
    }
    div.stButton > button:hover, div.stDownloadButton > button:hover {
        border-color: #00E676 !important;
        color: #00E676 !important;
        background-color: rgba(0, 230, 118, 0.04) !important;
        transform: translateY(-1.5px) !important;
        box-shadow: 0 4px 12px rgba(0, 230, 118, 0.12) !important;
    }
    div.stButton > button:active, div.stDownloadButton > button:active {
        transform: translateY(0px) !important;
    }

    /* 6. Color indicators & pills */
    .color-green {
        color: #00C805 !important;
    }
    .color-red {
        color: #FF3B30 !important;
    }
    .color-gray { color: #8A94A6 !important; }

    .pill-pos { background: rgba(0, 200, 5, 0.15); color: #00C805; padding: 2px 6px; font-weight: 600; border-radius: 3px; font-size: 11px; display: inline-block; }
    .pill-neg { background: rgba(255, 59, 48, 0.15); color: #FF3B30; padding: 2px 6px; font-weight: 600; border-radius: 3px; font-size: 11px; display: inline-block; }
    .pill-neut { background: rgba(138, 148, 166, 0.15); color: #8A94A6; padding: 2px 6px; font-weight: 600; border-radius: 3px; font-size: 11px; display: inline-block; }

    .badge-strong-buy { background: rgba(0, 200, 5, 0.15); color: #00C805; padding: 4px 8px; border-radius: 3px; font-weight: 700; font-size: 12px; border: 1px solid #00C805; }
    .badge-buy { background: rgba(0, 200, 5, 0.15); color: #00C805; padding: 4px 8px; border-radius: 3px; font-weight: 700; font-size: 12px; border: 1px solid #00C805; }
    .badge-hold { background: rgba(138, 148, 166, 0.15); color: #8A94A6; padding: 4px 8px; border-radius: 3px; font-weight: 700; font-size: 12px; border: 1px solid #8A94A6; }
    .badge-sell { background: rgba(255, 59, 48, 0.15); color: #FF3B30; padding: 4px 8px; border-radius: 3px; font-weight: 700; font-size: 12px; border: 1px solid #FF3B30; }

    .sent-bullish { color: #00C805; font-weight: 700; font-size: 11px; }
    .sent-bearish { color: #FF3B30; font-weight: 700; font-size: 11px; }
    .sent-neutral { color: #8A94A6; font-weight: 700; font-size: 11px; }

    /* Vol gauge bar */
    .vol-track { background: #1E2433; border-radius: 3px; height: 8px; width: 100%; position: relative; margin: 6px 0; }
    .vol-fill { height: 8px; border-radius: 3px; position: absolute; left: 0; top: 0; }
    .vol-marker { width: 3px; height: 14px; background: #FFFFFF; border-radius: 1px; position: absolute; top: -3px; }

    /* Scanner table rows */
    .scan-row { display: flex; justify-content: space-between; border-bottom: 1px solid #1E2433; padding: 6px 0; font-size: 13px; align-items: center; }
    .scan-row:last-child { border-bottom: none; }

    /* News links */
    .news-link { color: #FFFFFF; text-decoration: none; font-size: 13px; font-weight: 600; transition: color 0.15s ease-in-out; }
    .news-link:hover { text-decoration: none; color: #00C805 !important; }
    .tl-item { padding: 6px 0; border-bottom: 1px solid #1E2433; }
    .tl-item:last-child { border-bottom: none; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================================================
# SESSION STATE & ROUTING
# ==============================================================================
if "current_tab" not in st.session_state:
    st.session_state["current_tab"] = "MARKET_HOME"
if "active_ticker" not in st.session_state:
    st.session_state["active_ticker"] = "AAPL"
if "highlighted_pattern" not in st.session_state:
    st.session_state["highlighted_pattern"] = ""
if "results" not in st.session_state:
    st.session_state["results"] = []
if "portfolio_cash" not in st.session_state:
    st.session_state["portfolio_cash"] = 100000.00
if "portfolio_holdings" not in st.session_state:
    st.session_state["portfolio_holdings"] = {}
if "portfolio_history" not in st.session_state:
    st.session_state["portfolio_history"] = []
if "trade_order_type" not in st.session_state:
    st.session_state["trade_order_type"] = "BUY"

# Handle Query Parameters
if st.query_params:
    q_params = st.query_params
    updated = False
    if "tab" in q_params:
        tab_val = q_params["tab"]
        if tab_val in ["AI_AGENT_RESEARCH", "AI AGENT RESEARCH", "RESEARCH"]:
            st.session_state["current_tab"] = "RESEARCH"
        else:
            st.session_state["current_tab"] = tab_val
        updated = True
    if "ticker" in q_params:
        st.session_state["active_ticker"] = q_params["ticker"].strip().upper()
        st.session_state["current_tab"] = "RESEARCH"
        updated = True
    if updated:
        st.query_params.clear()
        st.rerun()

current_tab = st.session_state["current_tab"]

# ==============================================================================
# HORIZONTAL TOP NAVIGATION
# ==============================================================================
# Build the nav links HTML string
_nav_links = ""
for _tid, _tname in [
    ("MARKET_HOME", "MARKET HOME"),
    ("NEWS", "NEWS"),
    ("MARKETS", "MARKETS"),
    ("RESEARCH", "RESEARCH"),
    ("TRADE_DESK", "SIMULATION"),
    ("PATTERN_GUIDE", "PATTERN GUIDE")
]:
    _active = (current_tab == _tid)
    _style = "color:#FFFFFF;border-bottom:3px solid #00C805;" if _active else "color:#8A94A6;border-bottom:3px solid transparent;"
    _out = "this.style.color='#8A94A6'" if not _active else "this.style.color='#FFFFFF'"
    _nav_links += (
        f'<a href="/?tab={_tid}" target="_self" style="'
        f'text-decoration:none;font-size:12px;font-weight:600;'
        f'height:100%;display:flex;align-items:center;'
        f'padding:0 14px;box-sizing:border-box;'
        f'transition:color 0.2s ease-in-out;{_style}"'
        f' onmouseover="this.style.color=\'#FFFFFF\'"'
        f' onmouseout="{_out}">{_tname}</a>'
    )

# Inject the nav bar via st.html
st.html(
    f'<div style="'
    f'position:fixed;top:0;left:0;right:0;height:48px;'
    f'background-color:#1A1F2C;border-bottom:1px solid #2A3142;'
    f'z-index:99999;display:flex;align-items:center;'
    f'justify-content:flex-start;padding:0 24px;'
    f'box-shadow:0px 2px 8px rgba(0,0,0,0.3);'
    f'font-family:\'Inter\',-apple-system,sans-serif;box-sizing:border-box;">'
    f'<div style="font-size:14px;font-weight:700;color:#FFFFFF;'
    f'letter-spacing:1.5px;margin-right:32px;text-transform:uppercase;">QUANTVIZ TERMINAL</div>'
    f'<div style="display:flex;gap:4px;height:100%;align-items:center;">'
    f'{_nav_links}'
    f'</div></div>'
)

# ==============================================================================

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

@st.cache_data(ttl=60)
def get_live_price(symbol: str) -> float:
    symbol = symbol.strip().upper()
    if not symbol:
        return 0.0
    try:
        t = yf.Ticker(symbol)
        df = t.history(period="1d")
        if not df.empty:
            return float(df["Close"].iloc[-1])
    except Exception:
        pass
    return 0.0

@st.cache_data(ttl=60)
def get_live_prices_batch(symbols: list) -> dict:
    if not symbols:
        return {}
    symbols = [s.strip().upper() for s in symbols]
    try:
        data = yf.download(symbols, period="1d", group_by="ticker", progress=False)
        prices = {}
        for sym in symbols:
            if len(symbols) == 1:
                if not data.empty:
                    prices[sym] = float(data["Close"].iloc[-1])
            else:
                if sym in data and not data[sym].empty:
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
    core = list(HEATMAP_STOCKS.keys())
    try:
        data = yf.download(core, period="65d", group_by="ticker", progress=False)
        records = []
        for tk in core:
            if tk in data:
                df = data[tk].dropna()
                if len(df) >= 5:
                    cl = float(df["Close"].iloc[-1])
                    cp = float(df["Close"].iloc[-2])
                    chg = ((cl - cp) / cp) * 100
                    vol_now = float(df["Volume"].iloc[-1])
                    vol_avg = float(df["Volume"].tail(60).mean()) if len(df) >= 60 else float(df["Volume"].mean())
                    vol_ratio = vol_now / (vol_avg + 1) 
                    hi_52 = float(df["High"].max())
                    lo_52 = float(df["Low"].min())
                    is_hi = cl >= hi_52 * 0.98
                    is_lo = cl <= lo_52 * 1.02
                    records.append({
                        "ticker": tk, "close": cl, "change": chg,
                        "volume": vol_now, "vol_ratio": vol_ratio,
                        "is_hi": is_hi, "is_lo": is_lo
                    })
        rdf = pd.DataFrame(records)
        if rdf.empty:
            return {"gainers": [], "losers": [], "unusual_vol": [], "new_hi": [], "new_lo": []}

        gainers = rdf.sort_values("change", ascending=False).head(10).to_dict("records")
        losers = rdf.sort_values("change", ascending=True).head(10).to_dict("records")
        unusual = rdf[rdf["vol_ratio"] > 2.0].sort_values("vol_ratio", ascending=False).head(10).to_dict("records")
        new_hi = rdf[rdf["is_hi"]].to_dict("records")
        new_lo = rdf[rdf["is_lo"]].to_dict("records")
        return {"gainers": gainers, "losers": losers, "unusual_vol": unusual, "new_hi": new_hi, "new_lo": new_lo}
    except Exception:
        pass
    return {"gainers": [], "losers": [], "unusual_vol": [], "new_hi": [], "new_lo": []}

@st.cache_data(ttl=300)
def get_futures_commodities() -> list:
    symbols = ["ES=F", "YM=F", "NQ=F", "GC=F", "CL=F", "SI=F", "^TNX"]
    names = {
        "ES=F": "S&P 500 Futures",
        "YM=F": "Dow Futures",
        "NQ=F": "Nasdaq Futures",
        "GC=F": "Gold",
        "CL=F": "Crude Oil",
        "SI=F": "Silver",
        "^TNX": "10-Year Yield"
    }
    try:
        data = yf.download(symbols, period="2d", group_by="ticker", progress=False)
        records = []
        for sym in symbols:
            if sym in data and not data[sym].empty:
                df = data[sym].dropna()
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
        return records
    except Exception:
        pass
    return [
        {"symbol": "ES=F", "name": "S&P 500 Futures", "price": 5420.25, "change": 12.50, "pct": 0.23},
        {"symbol": "YM=F", "name": "Dow Futures", "price": 39510.00, "change": -45.00, "pct": -0.11},
        {"symbol": "NQ=F", "name": "Nasdaq Futures", "price": 19250.75, "change": 88.20, "pct": 0.46},
        {"symbol": "GC=F", "name": "Gold", "price": 2354.20, "change": 14.80, "pct": 0.63},
        {"symbol": "CL=F", "name": "Crude Oil", "price": 81.35, "change": -0.42, "pct": -0.51},
        {"symbol": "SI=F", "name": "Silver", "price": 30.25, "change": 0.18, "pct": 0.60},
        {"symbol": "^TNX", "name": "10-Year Yield", "price": 4.225, "change": 0.015, "pct": 0.36}
    ]

def get_recent_insiders() -> list:
    names = [
        ("AAPL", "Cook Timothy D", "CEO", "Sale", 175.50, 50000),
        ("MSFT", "Nadella Satya", "CEO", "Sale", 420.10, 15000),
        ("NVDA", "Huang Jen Hsun", "CEO", "Sale", 126.30, 120000),
        ("TSLA", "Musk Elon", "CEO", "Buy", 172.50, 200000),
        ("AMZN", "Bezos Jeffrey P", "Director", "Sale", 188.40, 80000),
        ("META", "Zuckerberg Mark", "CEO", "Sale", 485.60, 10000),
        ("GOOGL", "Pichai Sundar", "CEO", "Sale", 177.20, 25000),
        ("NFLX", "Hastings Reed", "Director", "Sale", 620.50, 8000),
        ("JPM", "Dimon Jamie", "CEO", "Sale", 195.30, 30000),
        ("LLY", "Ricks David A", "CEO", "Sale", 820.00, 5000)
    ]
    records = []
    base_date = datetime.now()
    for idx, (tk, name, title, tx, price, shares) in enumerate(names):
        date_str = (base_date - timedelta(days=idx)).strftime("%b %d")
        val = price * shares
        records.append({
            "ticker": tk,
            "owner": name,
            "relation": title,
            "date": date_str,
            "type": tx,
            "price": price,
            "shares": shares,
            "value": val
        })
    return records

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
    symbol = symbol.strip().upper()
    try:
        t = yf.Ticker(symbol)
        info = t.info
        return {
            "previous_close": info.get("previousClose", 0.0) or 0.0,
            "open": info.get("open", 0.0) or 0.0,
            "bid": info.get("bid", 0.0) or 0.0,
            "ask": info.get("ask", 0.0) or 0.0,
            "volume": info.get("volume", 0.0) or 0.0,
            "avg_volume": info.get("averageVolume", 0.0) or 0.0,
            "market_cap": info.get("marketCap", 0.0) or 0.0,
            "long_name": info.get("longName", symbol) or symbol,
            "beta": info.get("beta", 0.0) or 0.0,
            "pe_ratio": info.get("trailingPE", 0.0) or 0.0,
            "eps": info.get("trailingEps", 0.0) or 0.0,
            "day_low": info.get("dayLow", 0.0) or 0.0,
            "day_high": info.get("dayHigh", 0.0) or 0.0,
            "fifty_two_low": info.get("fiftyTwoWeekLow", 0.0) or 0.0,
            "fifty_two_high": info.get("fiftyTwoWeekHigh", 0.0) or 0.0
        }
    except Exception:
        pass
    return {
        "previous_close": 0.0,
        "open": 0.0,
        "bid": 0.0,
        "ask": 0.0,
        "volume": 0.0,
        "avg_volume": 0.0,
        "market_cap": 0.0,
        "long_name": symbol,
        "beta": 0.0,
        "pe_ratio": 0.0,
        "eps": 0.0,
        "day_low": 0.0,
        "day_high": 0.0,
        "fifty_two_low": 0.0,
        "fifty_two_high": 0.0
    }

@st.cache_data(ttl=600)
def get_rss_news(symbol: str) -> list:
    """Fetch news headlines from Yahoo Finance RSS feed and calculate phrase-based sentiment."""
    symbol = symbol.strip().upper()
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            xml_data = resp.read()
        root = ET.fromstring(xml_data)
        items = root.findall(".//item")
        parsed = []
        
        pos_phrases = ["beating expectations", "surpassing guidance", "strategic breakthrough", "increased allocation", "upgrade", "growth acceleration", "support holds"]
        neg_phrases = ["regulatory probe", "supply constraints", "device costs rising", "revenue miss", "guidance cut", "downgrade", "resistance ceiling holds"]
        
        for item in items[:10]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            source = (item.findtext("source") or "Yahoo Finance").strip()
            summary_snippet = (item.findtext("description") or "").strip()
            
            if not title:
                continue
                
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
                "date": pub_date,  # compatibility key
                "source": source,
                "summary_snippet": summary_snippet,
                "sentiment_score": sa,
                "badge": badge,
                "class": bcls
            })
        return parsed
    except Exception:
        pass
    return []

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
    
    # Split description into nice bullets/sentences for structured captions
    desc = n.get('summary_snippet', '') or ''
    sentences = [s.strip() for s in desc.split('.') if s.strip()]
    bullet_list = ""
    for s in sentences[:3]:
        bullet_list += f"<li style='margin-bottom: 4px; font-size: 13px; color: #8A94A6; line-height: 1.4; font-family: \"Inter\", sans-serif;'>{s}.</li>"
    if not bullet_list:
        bullet_list = f"<li style='margin-bottom: 4px; font-size: 13px; color: #8A94A6; font-family: \"Inter\", sans-serif;'>Latest market catalyst details.</li>"
        
    badge_html = f"""<span class="{n.get('class', 'sent-neutral')}" style="margin-left: auto; font-size: 10px; font-weight: 700; border-radius: 3px; padding: 1px 6px; background: rgba(138,148,166,0.1); border: 1px solid currentColor;">{n.get('badge', 'NEUTRAL')}</span>"""
    
    header_html = f"""
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap;">
        <img src="https://www.google.com/s2/favicons?sz=64&domain={dom}" style="width: 18px; height: 18px; border-radius: 3px;" />
        <span style="font-size: 11px; font-weight: 700; color: #FFFFFF; text-transform: uppercase; font-family: 'JetBrains Mono', monospace;">{n.get('source', 'NEWS')}</span>
        <span style="font-size: 11px; color: #8A94A6;">&middot; {n.get('pub_date', '')}</span>
        {badge_html}
    </div>
    """
    
    title_html = f"""
    <div style="margin-bottom: 10px;">
        <a href="{n.get('link', '#')}" target="_blank" style="font-size: 16px; font-weight: 700; color: #58A6FF; text-decoration: none; font-family: 'Inter', sans-serif; line-height: 1.3; transition: color 0.15s ease-in-out;" 
           onmouseover="this.style.color='#00C805'" onmouseout="this.style.color='#58A6FF'">
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
        <div style="background-color: #11151F; border: 1px solid #1E2433; border-radius: 8px; margin-bottom: 16px; display: flex; flex-direction: column; overflow: hidden; transition: border-color 0.2s ease-in-out;">
            <img src="{img_b64}" style="width: 100%; height: 210px; object-fit: cover; border-bottom: 1px solid #1E2433;" />
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
        <div style="background-color: #11151F; border: 1px solid #1E2433; border-radius: 8px; padding: 16px; margin-bottom: 16px; display: flex; gap: 16px; align-items: stretch; transition: border-color 0.2s ease-in-out;">
            <img src="{img_b64}" style="width: 220px; height: 150px; border-radius: 4px; object-fit: cover; border: 1px solid #1E2433; flex-shrink: 0;" />
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
    df = res["prices"]
    if df.empty or len(df) < 20:
        return {
            "rsi": 50.0, "support": 0.0, "resistance": 0.0,
            "crossover_status": "Neutral", "action_label": "HOLD",
            "action_class": "badge-hold", "ratio_20": 1.0, "ratio_60": 1.0,
            "quant_score": 50.0, "position_advice": "Allocate no more than 0.0% of capital. Annualized volatility: 0.0%.", "channel": "N/A",
            "sma_200": 0.0, "macd": 0.0, "macd_signal": 0.0, "macd_hist": 0.0,
            "ema_9": 0.0, "ema_20": 0.0, "volatility": 0.0, "s_total": 0.0,
            "sma_20": 0.0, "sma_60": 0.0
        }
    close_series = df["Close"]
    P = close_series.tolist()
    price = P[-1]
    
    # 20 SMA & 60 SMA
    sma20_val = sum(P[-20:]) / 20.0
    sma60_val = sum(P[-60:]) / 60.0
    sma200_val = sum(P[-200:]) / 200.0 if len(P) >= 200 else 0.0
    
    # RSI
    rsi_val = calculate_rsi(close_series, 14)
    
    # Annualized Volatility
    if len(P) >= 61:
        sub_P = P[-61:]
        log_returns = [np.log(sub_P[i] / sub_P[i-1]) for i in range(1, len(sub_P))]
        sigma = np.std(log_returns, ddof=1)
        volatility = sigma * np.sqrt(252) * 100
    elif len(P) >= 2:
        log_returns = [np.log(P[i] / P[i-1]) for i in range(1, len(P))]
        sigma = np.std(log_returns, ddof=1) if len(log_returns) > 1 else 0.0
        volatility = sigma * np.sqrt(252) * 100
    else:
        volatility = 0.0
        
    # S_total from general rss news
    rss_news = get_rss_news(symbol)
    s_total = 0.0
    if rss_news:
        s_total = sum(n["sentiment_score"] for n in rss_news) / len(rss_news)
        
    # Support and resistance
    support_floor = float(df["Low"].tail(20).min())
    resistance_ceiling = float(df["High"].tail(20).max())
    
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
    ema9_val = float(calculate_ema(close_series, 9).iloc[-1]) if len(close_series) >= 9 else 0.0
    ema20_val = float(calculate_ema(close_series, 20).iloc[-1]) if len(close_series) >= 20 else 0.0
    channel = classify_channel(df)
    
    vol_cap = min(25.0, (10.0 / (volatility + 1e-9)) * 100) if volatility > 0 else 0.0
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

def make_sparkline(series, color="#58A6FF"):
    fig = go.Figure()
    is_up = (color == "#00C805")
    fillcolor = "rgba(0, 200, 5, 0.06)" if is_up else "rgba(255, 59, 48, 0.06)"
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

def render_scanner_header():
    return """
    <div style="display:flex; justify-content:space-between; border-bottom:1px solid #1E2433; padding: 6px 12px; font-size:11px; font-family: 'JetBrains Mono', monospace; color:#8A94A6; font-weight:700; background-color: #11151F; box-sizing: border-box;">
        <span style="width:55px; text-align:left;">Ticker</span>
        <span style="width:65px; text-align:right;">Price</span>
        <span style="width:60px; text-align:right;">Change</span>
        <span style="width:65px; text-align:right;">Volume</span>
        <span style="width:85px; text-align:right;">Signal</span>
    </div>
    """

def render_scanner_row(ticker, price, change, volume, signal, scls, row_index=0):
    bg_color = "#11151F" if row_index % 2 == 0 else "#161B26"
    sign = "+" if change >= 0 else ""
    cc = "color-green" if change >= 0 else "color-red"
    vol_str = format_volume(volume)
    return f"""
    <div class="scan-row" style="font-variant-numeric: tabular-nums; font-size: 12px; font-family: 'Inter', sans-serif; background-color: {bg_color}; padding: 6px 12px; display: flex; justify-content: space-between; border-bottom: 1px solid #1E2433; align-items: center; box-sizing: border-box;">
        <a href="/?tab=RESEARCH&ticker={ticker}" target="_self" style="font-weight:700; color:#58A6FF; width:55px; text-decoration:none;">{ticker}</a>
        <span style="color:#FFFFFF; width:65px; text-align:right; font-weight:600; font-family: 'JetBrains Mono', monospace;">${price:.2f}</span>
        <span class="{cc}" style="width:60px; text-align:right; font-weight:700; font-family: 'JetBrains Mono', monospace;">{sign}{change:.2f}%</span>
        <span style="color:#8A94A6; width:65px; text-align:right; font-weight:500; font-family: 'JetBrains Mono', monospace;">{vol_str}</span>
        <span class="{scls}" style="width:85px; text-align:right; font-size:10px; font-weight:700; font-family: 'JetBrains Mono', monospace;">{signal}</span>
    </div>
    """

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
            colorscale=[[0, "#FF3B30"], [0.5, "#11151F"], [1, "#00C805"]],
            cmin=-3.0,
            cmax=3.0,
            cmid=0.0,
            showscale=False,
            line=dict(color="#1E2433", width=1)
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
        font=dict(family="'Inter', -apple-system, sans-serif", color="#ffffff")
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
        increasing=dict(line=dict(color="#00C805", width=2), fillcolor="#00C805"),
        decreasing=dict(line=dict(color="#FF3B30", width=2), fillcolor="#FF3B30")
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=sma20.index, y=sma20, name="SMA 20", line=dict(color="rgba(88,166,255,0.6)", width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=sma60.index, y=sma60, name="SMA 60", line=dict(color="rgba(139,148,158,0.5)", width=1.5)), row=1, col=1)
    if not sma200.dropna().empty:
        fig.add_trace(go.Scatter(x=sma200.index, y=sma200, name="SMA 200", line=dict(color="rgba(245,166,35,0.6)", width=1.5, dash="dot")), row=1, col=1)
        
    # 2. Volume
    colors = ["#00C805" if cl >= op else "#FF3B30" for op, cl in zip(fdf["Open"], fdf["Close"])]
    fig.add_trace(go.Bar(
        x=fdf.index, y=fdf["Volume"],
        name="Volume", marker_color=colors, showlegend=False
    ), row=2, col=1)
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(t=10, b=10, l=10, r=10), height=550,
        dragmode='pan',
        font=dict(color="#8A94A6", family="'Inter', -apple-system, sans-serif", size=11),
        hovermode="x unified"
    )
    fig.update_xaxes(
        showgrid=True, gridcolor="#1E2433", showline=True, linecolor="#2A3142", ticks="outside",
        showspikes=True, spikethickness=1, spikedash="dash", spikemode="across", spikecolor="#8A94A6"
    )
    fig.update_xaxes(rangeslider_visible=False) # Hide range slider on all subplots
    fig.update_yaxes(
        showgrid=True, gridcolor="#1E2433", side="right", showline=True, linecolor="#2A3142", ticks="outside",
        showspikes=True, spikethickness=1, spikedash="dash", spikemode="across", spikecolor="#8A94A6"
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
    # ── INDEX SNAPSHOT MATRIX (7 BENCHMARKS) ──
    with st.spinner("Loading indices..."):
        idx_data = get_index_snapshots()
    if idx_data:
        indices_cols = st.columns(len(idx_data))
        for idx, item in enumerate(idx_data):
            with indices_cols[idx]:
                with st.container(border=True):
                    sign = "+" if item["pct"] >= 0 else ""
                    pts_sign = "+" if item["pts"] >= 0 else ""
                    cc_text = "#00C805" if item["pct"] >= 0 else "#FF3B30"
                    
                    header_html = f"""
                    <div style="display:flex; align-items:center; justify-content:space-between; font-variant-numeric: tabular-nums; font-family:\'Inter\',-apple-system,sans-serif; margin-bottom: 4px; gap: 4px; width: 100%;">
                        <span style="color:#8A94A6; font-weight:700; font-size:11px; text-transform:uppercase;">{item['name']}</span>
                        <span style="color:#ffffff; font-weight:700; font-size:12px;">{item['close']:,.2f}</span>
                        <span style="color:{cc_text}; font-weight:700; font-size:11px;">{pts_sign}{item['pts']:,.2f}</span>
                        <span style="color:{cc_text}; font-weight:700; font-size:11px;">{sign}{item['pct']:.2f}%</span>
                    </div>
                    """
                    st.html(header_html)
                    fig = make_sparkline(item["series"], color=cc_text)
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── 3-COLUMN FINVIZ MATRIX GRID ──
    col1, col2, col3 = st.columns([1, 1.4, 1])

    with col1:
        st.subheader("Top Gainers")
        st.markdown("<div class='fintech-card' style='padding:0px !important;'>", unsafe_allow_html=True)
        st.markdown(render_scanner_header(), unsafe_allow_html=True)
        with st.spinner("Scanning gainers..."):
            scanners = get_market_scanners()
        if scanners["gainers"]:
            for idx, r in enumerate(scanners["gainers"]):
                st.markdown(render_scanner_row(r["ticker"], r["close"], r["change"], r["volume"], "GAINER", "pill-pos", row_index=idx), unsafe_allow_html=True)
        else:
            st.markdown("<div style='color:#888888; font-size:11px; padding: 6px;'>No data</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.subheader("Top Losers")
        st.markdown("<div class='fintech-card' style='padding:0px !important;'>", unsafe_allow_html=True)
        st.markdown(render_scanner_header(), unsafe_allow_html=True)
        if scanners["losers"]:
            for idx, r in enumerate(scanners["losers"]):
                st.markdown(render_scanner_row(r["ticker"], r["close"], r["change"], r["volume"], "LOSER", "pill-neg", row_index=idx), unsafe_allow_html=True)
        else:
            st.markdown("<div style='color:#888888; font-size:11px; padding: 6px;'>No data</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.subheader("Market Heatmap")
        with st.spinner("Loading heatmap..."):
            hm_df = get_market_heatmap_data()
        if not hm_df.empty:
            st.markdown("<div class='fintech-card' style='padding:4px !important;'>", unsafe_allow_html=True)
            st.plotly_chart(make_heatmap_chart(hm_df), use_container_width=True, config={"displayModeBar": False})
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='fintech-card'><div style='color:#888888; font-size:11px;'>No heatmap data</div></div>", unsafe_allow_html=True)

    with col3:
        st.subheader("Unusual Volume")
        st.markdown("<div class='fintech-card' style='padding:0px !important;'>", unsafe_allow_html=True)
        st.markdown(render_scanner_header(), unsafe_allow_html=True)
        if scanners["unusual_vol"]:
            for idx, r in enumerate(scanners["unusual_vol"]):
                st.markdown(render_scanner_row(r["ticker"], r["close"], r["change"], r["volume"], "VOL SPIKE", "pill-neut", row_index=idx), unsafe_allow_html=True)
        else:
            st.markdown("<div style='color:#888888; font-size:11px; padding: 6px;'>No anomaly detected</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.subheader("New 52W Highs / Lows")
        st.markdown("<div class='fintech-card' style='padding:0px !important;'>", unsafe_allow_html=True)
        st.markdown(render_scanner_header(), unsafe_allow_html=True)
        if scanners["new_hi"] or scanners["new_lo"]:
            row_idx = 0
            for r in scanners["new_hi"][:3]:
                st.markdown(render_scanner_row(r["ticker"], r["close"], r["change"], r["volume"], "52W HIGH", "pill-pos", row_index=row_idx), unsafe_allow_html=True)
                row_idx += 1
            for r in scanners["new_lo"][:3]:
                st.markdown(render_scanner_row(r["ticker"], r["close"], r["change"], r["volume"], "52W LOW", "pill-neg", row_index=row_idx), unsafe_allow_html=True)
                row_idx += 1
        else:
            st.markdown("<div style='color:#888888; font-size:11px; padding: 6px;'>No breakout events</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── BOTTOM ROW WIDGETS (COMMODITIES & INSIDERS) ──
    row_futures, row_insiders = st.columns([1.4, 2.6])
    
    with row_futures:
        st.subheader("Futures & Commodities")
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
                <tr style="border-bottom:1px solid #1E2433; color:#8A94A6; font-size:11px; text-transform:uppercase; text-align:left;">
                    <th style="padding: 12px 14px; background-color: #11151F !important;">Index / Future</th>
                    <th style="padding: 12px 14px; text-align:right; background-color: #11151F !important;">Last Price</th>
                    <th style="padding: 12px 14px; text-align:right; background-color: #11151F !important;">Change</th>
                </tr>
            </thead>
            <tbody>
        """, unsafe_allow_html=True)
        for idx, item in enumerate(futures):
            c_val = item["pct"]
            sign = "+" if c_val >= 0 else ""
            badge_style = "background-color: rgba(0, 230, 118, 0.08); color: #00E676; border: 1px solid rgba(0, 230, 118, 0.2); padding: 4px 10px; border-radius: 4px; font-weight: 700; font-family: 'JetBrains Mono', monospace;" if c_val >= 0 else "background-color: rgba(255, 23, 68, 0.08); color: #FF1744; border: 1px solid rgba(255, 23, 68, 0.2); padding: 4px 10px; border-radius: 4px; font-weight: 700; font-family: 'JetBrains Mono', monospace;"
            st.markdown(f"""
                <tr style="border-bottom: 1px solid #1E2433;">
                    <td style="padding: 12px 14px; font-weight:700; color:#FFFFFF;">{item['name']} <span style="font-size:9px; color:#8A94A6; font-family:'JetBrains Mono', monospace;">({item['symbol']})</span></td>
                    <td style="padding: 12px 14px; text-align:right; font-weight:700; color:#FFFFFF; font-family:'JetBrains Mono', monospace;">{item['price']:,.2f}</td>
                    <td style="padding: 12px 14px; text-align:right;"><span style="{badge_style}">{sign}{c_val:.2f}%</span></td>
                </tr>
            """, unsafe_allow_html=True)
        st.markdown("</tbody></table></div>", unsafe_allow_html=True)

    with row_insiders:
        st.subheader("Recent Insider Transactions")
        insiders = get_recent_insiders()
        st.markdown("<div class='fintech-card' style='padding:0px !important;'>", unsafe_allow_html=True)
        st.markdown("""
        <table class="fintech-table" style="width:100%; border-collapse:collapse; font-size:12px; font-variant-numeric: tabular-nums;">
            <thead>
                <tr style="border-bottom:1px solid #1E2433; color:#8A94A6; font-size:11px; text-transform:uppercase; text-align:left;">
                    <th style="padding: 12px 14px; background-color: #11151F !important;">Ticker</th>
                    <th style="padding: 12px 14px; background-color: #11151F !important;">Insider Owner</th>
                    <th style="padding: 12px 14px; background-color: #11151F !important;">Relationship</th>
                    <th style="padding: 12px 14px; text-align:center; background-color: #11151F !important;">Trade</th>
                    <th style="padding: 12px 14px; text-align:right; background-color: #11151F !important;">Cost</th>
                    <th style="padding: 12px 14px; text-align:right; background-color: #11151F !important;">Shares</th>
                    <th style="padding: 12px 14px; text-align:right; background-color: #11151F !important;">Value ($)</th>
                </tr>
            </thead>
            <tbody>
        """, unsafe_allow_html=True)
        for idx, item in enumerate(insiders):
            action_style = "background-color: rgba(0, 230, 118, 0.08); color: #00E676; border: 1px solid rgba(0, 230, 118, 0.2); padding: 4px 10px; border-radius: 4px; font-weight: 800; font-size: 10px;" if item["type"] == "Buy" else "background-color: rgba(255, 23, 68, 0.08); color: #FF1744; border: 1px solid rgba(255, 23, 68, 0.2); padding: 4px 10px; border-radius: 4px; font-weight: 800; font-size: 10px;"
            action_html = f'<span style="{action_style}">{item["type"].upper()}</span>'
            st.markdown(f"""
                <tr style="border-bottom: 1px solid #1E2433;">
                    <td style="padding: 12px 14px; font-weight:700;"><a href="/?tab=RESEARCH&ticker={item['ticker']}" target="_self" style="color:#58A6FF; text-decoration:none; transition: color 0.15s;" onmouseover="this.style.color='#00E676'" onmouseout="this.style.color='#58A6FF'">{item['ticker']}</a></td>
                    <td style="padding: 12px 14px; color:#FFFFFF;">{item['owner']}</td>
                    <td style="padding: 12px 14px; color:#8A94A6;">{item['relation']}</td>
                    <td style="padding: 12px 14px; text-align:center;">{action_html}</td>
                    <td style="padding: 12px 14px; text-align:right; font-family:'JetBrains Mono', monospace; color:#FFFFFF;">${item['price']:.2f}</td>
                    <td style="padding: 12px 14px; text-align:right; font-family:'JetBrains Mono', monospace; color:#FFFFFF;">{item['shares']:,}</td>
                    <td style="padding: 12px 14px; text-align:right; font-family:'JetBrains Mono', monospace; font-weight:700; color:#FFFFFF;">${item['value']:,.0f}</td>
                </tr>
            """, unsafe_allow_html=True)
        st.markdown("</tbody></table></div>", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# TAB 3: NEWS
# ──────────────────────────────────────────────────────────────────────────────
elif current_tab == "NEWS":
    st.subheader("Latest Financial News & Market Catalyst Consensus")
    
    col_left, col_right = st.columns([2.6, 1.4])
    
    with st.spinner("Retrieving news wires..."):
        news = get_rss_news("^GSPC")
        
    with col_left:
        if news:
            for idx, n in enumerate(news):
                st.html(clean_html(render_rich_news_card(n, idx)))
        else:
            st.markdown("<div class='fintech-card'><div style='color:#8A94A6; font-size:12px;'>No general news available currently</div></div>", unsafe_allow_html=True)
            
    with col_right:
        st.subheader("Market Sentiment Consensus")
        if news:
            scores = [n["sentiment_score"] for n in news]
            avg_score = sum(scores) / len(scores) if scores else 0.0
            bullish_cnt = sum(1 for n in news if n["badge"] == "BULLISH")
            bearish_cnt = sum(1 for n in news if n["badge"] == "BEARISH")
            neutral_cnt = sum(1 for n in news if n["badge"] == "NEUTRAL")
            
            consensus = "MIXED"
            cc_color = "#8A94A6"
            if avg_score > 0.05:
                consensus = "BULLISH ACCELERATION"
                cc_color = "#00C805"
            elif avg_score < -0.05:
                consensus = "BEARISH RISK"
                cc_color = "#FF3B30"
                
            st.markdown(f"""
            <div class="fintech-card" style="margin-bottom:12px;">
                <div style="font-size:10px; color:#8A94A6; font-weight:700; text-transform:uppercase; margin-bottom:4px;">Average Score Consensus</div>
                <div style="font-size:24px; font-weight:800; color:{cc_color}; font-family:'JetBrains Mono', monospace; margin-bottom:4px;">{avg_score:+.2f}</div>
                <div style="font-size:12px; font-weight:700; color:{cc_color};">{consensus}</div>
                
                <div style="border-top:1px solid #1E2433; margin-top:12px; padding-top:12px; display:flex; justify-content:space-between; font-size:11px; font-family:'JetBrains Mono', monospace;">
                    <div><span style="color:#00C805; font-weight:700;">{bullish_cnt}</span> Bullish</div>
                    <div><span style="color:#8A94A6; font-weight:700;">{neutral_cnt}</span> Neutral</div>
                    <div><span style="color:#FF3B30; font-weight:700;">{bearish_cnt}</span> Bearish</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Simple Plotly Gauge Chart for Sentiment
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = avg_score,
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "Sentiment Index", 'font': {'size': 11, 'color': '#8A94A6'}},
                number = {'font': {'color': '#FFFFFF', 'size': 14}},
                gauge = {
                    'axis': {'range': [-1, 1], 'tickwidth': 1, 'tickcolor': "#8A94A6"},
                    'bar': {'color': cc_color},
                    'bgcolor': "#161B26",
                    'borderwidth': 1,
                    'bordercolor': "#1E2433",
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
            
        st.subheader("Trending Watchlist")
        trending_tickers = ["TSLA", "AAPL", "MSFT", "NVDA", "AMZN", "NFLX", "GOOGL", "META", "JPM", "V"]
        with st.spinner("Syncing watchlist..."):
            tr_prices = get_live_prices_batch(trending_tickers)
        st.markdown("<div class='fintech-card' style='padding:0px !important;'>", unsafe_allow_html=True)
        st.markdown("""
        <table class="fintech-table" style="width:100%; border-collapse:collapse; font-size:12px; font-variant-numeric: tabular-nums;">
            <thead>
                <tr style="border-bottom:1px solid #1E2433; color:#8A94A6; font-size:11px; text-transform:uppercase; text-align:left;">
                    <th style="padding: 12px 14px; background-color: #11151F !important;">Symbol</th>
                    <th style="padding: 12px 14px; text-align:right; background-color: #11151F !important;">Last Price</th>
                    <th style="padding: 12px 14px; text-align:right; background-color: #11151F !important;">Change</th>
                </tr>
            </thead>
            <tbody>
        """, unsafe_allow_html=True)
        for tk in trending_tickers:
            info = get_ticker_info(tk)
            chg = info.get("day_change_pct", 0.0) or 0.0
            price = tr_prices.get(tk, info.get("previous_close", 150.0))
            sign = "+" if chg >= 0 else ""
            badge_style = "background-color: rgba(0, 230, 118, 0.08); color: #00E676; border: 1px solid rgba(0, 230, 118, 0.2); padding: 4px 10px; border-radius: 4px; font-weight: 700; font-family: 'JetBrains Mono', monospace;" if chg >= 0 else "background-color: rgba(255, 23, 68, 0.08); color: #FF1744; border: 1px solid rgba(255, 23, 68, 0.2); padding: 4px 10px; border-radius: 4px; font-weight: 700; font-family: 'JetBrains Mono', monospace;"
            st.markdown(f"""
                <tr style="border-bottom: 1px solid #1E2433;">
                    <td style="padding: 12px 14px; font-weight:700;"><a href="/?tab=RESEARCH&ticker={tk}" target="_self" style="color:#58A6FF; text-decoration:none; transition: color 0.15s;" onmouseover="this.style.color='#00E676'" onmouseout="this.style.color='#58A6FF'">{tk}</a></td>
                    <td style="padding: 12px 14px; text-align:right; font-weight:700; color:#FFFFFF; font-family:'JetBrains Mono', monospace;">${price:,.2f}</td>
                    <td style="padding: 12px 14px; text-align:right;"><span style="{badge_style}">{sign}{chg:.2f}%</span></td>
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
                    <tr style="border-bottom:1px solid #1E2433; color:#8A94A6; font-size:11px; text-transform:uppercase; text-align:left;">
                        <th style="padding: 12px 14px; background-color: #11151F !important;">Sector / ETF</th>
                        <th style="padding: 12px 14px; text-align:center; background-color: #11151F !important;">Momentum</th>
                        <th style="padding: 12px 14px; text-align:right; background-color: #11151F !important;">1D Return</th>
                    </tr>
                </thead>
                <tbody>
            """, unsafe_allow_html=True)
            for item in sectors:
                c = item["change"]
                mom = item["momentum"]
                sign = "+" if c >= 0 else ""
                mom_color = "#00E676" if mom == "UP" else ("#FF1744" if mom == "DOWN" else "#8A94A6")
                badge_style = "background-color: rgba(0, 230, 118, 0.08); color: #00E676; border: 1px solid rgba(0, 230, 118, 0.2); padding: 4px 10px; border-radius: 4px; font-weight: 700; font-family: 'JetBrains Mono', monospace;" if c >= 0 else "background-color: rgba(255, 23, 68, 0.08); color: #FF1744; border: 1px solid rgba(255, 23, 68, 0.2); padding: 4px 10px; border-radius: 4px; font-weight: 700; font-family: 'JetBrains Mono', monospace;"
                st.markdown(f"""
                    <tr style="border-bottom: 1px solid #1E2433;">
                        <td style="padding: 12px 14px; font-weight:700;"><span style="color:#58A6FF;">{item['name']}</span> <span style="font-size:10px; color:#8A94A6; font-family:'JetBrains Mono', monospace;">({item['ticker']})</span></td>
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
                number={'suffix': "%", 'font': {'color': '#FFFFFF', 'size': 18, 'family': 'JetBrains Mono'}},
                title={'text': "Short-Term (20D SMA)", 'font': {'size': 10, 'color': '#8A94A6'}},
                gauge={
                    'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': '#8A94A6'},
                    'bar': {'color': '#00E676'},
                    'bgcolor': "#161B26",
                    'borderwidth': 1,
                    'bordercolor': "#1E2433",
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
                number={'suffix': "%", 'font': {'color': '#FFFFFF', 'size': 18, 'family': 'JetBrains Mono'}},
                title={'text': "Medium-Term (60D SMA)", 'font': {'size': 10, 'color': '#8A94A6'}},
                gauge={
                    'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': '#8A94A6'},
                    'bar': {'color': '#58A6FF'},
                    'bgcolor': "#161B26",
                    'borderwidth': 1,
                    'bordercolor': "#1E2433",
                    'steps': [
                        {'range': [0, 30], 'color': 'rgba(255, 59, 48, 0.1)'},
                        {'range': [30, 70], 'color': 'rgba(138, 148, 166, 0.1)'},
                        {'range': [70, 100], 'color': 'rgba(88, 166, 255, 0.1)'}
                    ]
                }
            ), row=1, col=2)
            
            fig_breadth.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(t=5, b=5, l=5, r=5), height=140
            )
            st.plotly_chart(fig_breadth, use_container_width=True, config={"displayModeBar": False})
            st.markdown("</div>", unsafe_allow_html=True)

        if sectors:
            # Horizontal Bar Chart for sectors returns
            names = [item["name"] for item in sectors]
            returns = [item["change"] for item in sectors]
            colors = ["#00E676" if r >= 0 else "#FF1744" for r in returns]
            fig_sector = go.Figure(go.Bar(
                x=returns, y=names, orientation='h',
                marker_color=colors, showlegend=False
            ))
            fig_sector.update_layout(
                title=dict(text="Sector Returns (1D Change)", font=dict(size=12, color="#8A94A6")),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(t=35, b=5, l=5, r=5), height=230
            )
            fig_sector.update_xaxes(showgrid=True, gridcolor="#1E2433", showline=True, linecolor="#2A3142", ticks="outside")
            fig_sector.update_yaxes(showgrid=False, showline=True, linecolor="#2A3142")
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
                <tr style="border-bottom:1px solid #1E2433; color:#8A94A6; text-transform:uppercase;">
                    <th style="padding: 10px 12px; text-align:left; background-color: #11151F !important;">Ticker</th>
                    <th style="padding: 10px 12px; text-align:right; background-color: #11151F !important;">Price</th>
                    <th style="padding: 10px 12px; text-align:right; background-color: #11151F !important;">Change</th>
                </tr>
            </thead>
            <tbody>
        """, unsafe_allow_html=True)
        for r in scanners["gainers"][:10]:
            chg = r["change"]
            badge_style = "background-color: rgba(0, 230, 118, 0.08); color: #00E676; border: 1px solid rgba(0, 230, 118, 0.2); padding: 3px 6px; border-radius: 4px; font-weight: 700; font-family: 'JetBrains Mono', monospace;"
            st.markdown(f"""
                <tr style="border-bottom: 1px solid #1E2433;">
                    <td style="padding: 10px 12px; font-weight:700;"><a href="/?tab=RESEARCH&ticker={r['ticker']}" target="_self" style="color:#58A6FF; text-decoration:none;">{r['ticker']}</a></td>
                    <td style="padding: 10px 12px; text-align:right; color:#FFFFFF; font-family:'JetBrains Mono', monospace;">${r['close']:.2f}</td>
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
                <tr style="border-bottom:1px solid #1E2433; color:#8A94A6; text-transform:uppercase;">
                    <th style="padding: 10px 12px; text-align:left; background-color: #11151F !important;">Ticker</th>
                    <th style="padding: 10px 12px; text-align:right; background-color: #11151F !important;">Price</th>
                    <th style="padding: 10px 12px; text-align:right; background-color: #11151F !important;">Change</th>
                </tr>
            </thead>
            <tbody>
        """, unsafe_allow_html=True)
        for r in scanners["losers"][:10]:
            chg = r["change"]
            badge_style = "background-color: rgba(255, 23, 68, 0.08); color: #FF1744; border: 1px solid rgba(255, 23, 68, 0.2); padding: 3px 6px; border-radius: 4px; font-weight: 700; font-family: 'JetBrains Mono', monospace;"
            st.markdown(f"""
                <tr style="border-bottom: 1px solid #1E2433;">
                    <td style="padding: 10px 12px; font-weight:700;"><a href="/?tab=RESEARCH&ticker={r['ticker']}" target="_self" style="color:#58A6FF; text-decoration:none;">{r['ticker']}</a></td>
                    <td style="padding: 10px 12px; text-align:right; color:#FFFFFF; font-family:'JetBrains Mono', monospace;">${r['close']:.2f}</td>
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
                <tr style="border-bottom:1px solid #1E2433; color:#8A94A6; text-transform:uppercase;">
                    <th style="padding: 10px 12px; text-align:left; background-color: #11151F !important;">Ticker</th>
                    <th style="padding: 10px 12px; text-align:right; background-color: #11151F !important;">Price</th>
                    <th style="padding: 10px 12px; text-align:right; background-color: #11151F !important;">Volume</th>
                </tr>
            </thead>
            <tbody>
        """, unsafe_allow_html=True)
        for r in scanners["unusual_vol"][:10]:
            vol_str = format_volume(r["volume"])
            st.markdown(f"""
                <tr style="border-bottom: 1px solid #1E2433;">
                    <td style="padding: 10px 12px; font-weight:700;"><a href="/?tab=RESEARCH&ticker={r['ticker']}" target="_self" style="color:#58A6FF; text-decoration:none;">{r['ticker']}</a></td>
                    <td style="padding: 10px 12px; text-align:right; color:#FFFFFF; font-family:'JetBrains Mono', monospace;">${r['close']:.2f}</td>
                    <td style="padding: 10px 12px; text-align:right; color:#8A94A6; font-family:'JetBrains Mono', monospace; font-weight:700;">{vol_str}</td>
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
        text_color = "#00C805" if ch >= 0 else "#FF3B30"
        
        st.markdown(f"""
        <div class="fintech-card">
            <div style="display:flex; align-items:baseline; gap:16px;">
                <span style="font-size:24px; font-weight:700; color:#FFFFFF;">{sym}</span>
                <span style="font-size:14px; color:#8A94A6;">{info['long_name']}</span>
                <span style="font-size:28px; font-weight:700; color:#FFFFFF;">${cl:.2f}</span>
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
                    <tr style="border-bottom: 1px solid #1E2433;">
                        <td style="color: #8A94A6; padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">Previous Close</td>
                        <td style="text-align: right; color: #FFFFFF; font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">${info['previous_close']:.2f}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1E2433;">
                        <td style="color: #8A94A6; padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">Open Price</td>
                        <td style="text-align: right; color: #FFFFFF; font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">${info['open']:.2f}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1E2433;">
                        <td style="color: #8A94A6; padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">Bid Price</td>
                        <td style="text-align: right; color: #FFFFFF; font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">${info['bid']:.2f}</td>
                    </tr>
                    <tr>
                        <td style="color: #8A94A6; padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">Ask Price</td>
                        <td style="text-align: right; color: #FFFFFF; font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">${info['ask']:.2f}</td>
                    </tr>
                </table>
                <!-- Column 2 -->
                <table style="width: 100%; border: none !important; border-collapse: collapse !important;">
                    <tr style="border-bottom: 1px solid #1E2433;">
                        <td style="color: #8A94A6; padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">Day's Range</td>
                        <td style="text-align: right; color: #FFFFFF; font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums; font-size: 11px;">${info['day_low']:.2f} - ${info['day_high']:.2f}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1E2433;">
                        <td style="color: #8A94A6; padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">52-Week Range</td>
                        <td style="text-align: right; color: #FFFFFF; font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums; font-size: 11px;">${info['fifty_two_low']:.2f} - ${info['fifty_two_high']:.2f}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1E2433;">
                        <td style="color: #8A94A6; padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">Volume</td>
                        <td style="text-align: right; color: #FFFFFF; font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">{format_volume(info['volume'])}</td>
                    </tr>
                    <tr>
                        <td style="color: #8A94A6; padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">Avg Volume</td>
                        <td style="text-align: right; color: #FFFFFF; font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">{format_volume(info['avg_volume'])}</td>
                    </tr>
                </table>
                <!-- Column 3 -->
                <table style="width: 100%; border: none !important; border-collapse: collapse !important;">
                    <tr style="border-bottom: 1px solid #1E2433;">
                        <td style="color: #8A94A6; padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">Market Cap</td>
                        <td style="text-align: right; color: #FFFFFF; font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">{format_market_cap(info['market_cap'])}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1E2433;">
                        <td style="color: #8A94A6; padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">Beta (5Y)</td>
                        <td style="text-align: right; color: #FFFFFF; font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">{info['beta']:.2f}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1E2433;">
                        <td style="color: #8A94A6; padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">PE Ratio</td>
                        <td style="text-align: right; color: #FFFFFF; font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">{info['pe_ratio']:.2f}</td>
                    </tr>
                    <tr>
                        <td style="color: #8A94A6; padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">EPS (TTM)</td>
                        <td style="text-align: right; color: #FFFFFF; font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">${info['eps']:.2f}</td>
                    </tr>
                </table>
                <!-- Column 4 -->
                <table style="width: 100%; border: none !important; border-collapse: collapse !important;">
                    <tr style="border-bottom: 1px solid #1E2433;">
                        <td style="color: #8A94A6; padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">14-Day RSI</td>
                        <td style="text-align: right; color: #FFFFFF; font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">{res.get('rsi', 50.0):.1f}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1E2433;">
                        <td style="color: #8A94A6; padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">20-Day SMA</td>
                        <td style="text-align: right; color: #FFFFFF; font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">${res.get('sma_20', 0.0):.2f}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #1E2433;">
                        <td style="color: #8A94A6; padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">60-Day SMA</td>
                        <td style="text-align: right; color: #FFFFFF; font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">${res.get('sma_60', 0.0):.2f}</td>
                    </tr>
                    <tr>
                        <td style="color: #8A94A6; padding: 6px 0 !important; font-size: 12px; text-transform: uppercase; font-weight:600;">Annualized Vol</td>
                        <td style="text-align: right; color: #FFFFFF; font-weight: 600; padding: 6px 0 !important; font-variant-numeric: tabular-nums;">{vol_pct:.1f}%</td>
                    </tr>
                </table>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Algorithmic Guidance Matrix
        guidance_label = act
        g_color = "#00C805" if "BUY" in guidance_label else ("#FF3B30" if "SELL" in guidance_label or "REDUCE" in guidance_label else "#8A94A6")
        
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
                <div style="font-size:10px; color:#8A94A6; font-weight:600; text-transform:uppercase;">Algorithmic Guidance</div>
                <div style="font-size:24px; font-weight:800; color:{g_color}; margin-top:8px;">{guidance_label}</div>
            </div>
            """, unsafe_allow_html=True)
        with rcol2:
            st.markdown(f"""
            <div class="fintech-card" style="min-height: 120px;">
                <div style="font-size:10px; color:#8A94A6; font-weight:600; text-transform:uppercase; margin-bottom:4px;">Micro-Summarization Breakdown</div>
                <div style="font-size:12px; color:#C9D1D9; line-height:1.4;">{summary_sentence}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="fintech-card" style="border-left: 3px solid #00C805; padding: 10px !important;">
            <div style="font-size:13px; color:#FFFFFF; font-weight:600;">Risk Protocol Status: Current asset exhibits a calculated 60-day annualized volatility metric of {vol:.1f}%. The position-sizing engine advises capping your theoretical capital deployment to exactly {vol_cap:.1f}% of total available portfolio equity balance sheets to shield capital from sudden price flips.</div>
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
                <tr style="border-bottom:1px solid #2A3142; color:#8A94A6; font-size:11px; text-transform:uppercase; text-align:left;">
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
            p_close = peer_prices.get(psym, pinfo.get("previous_close", 150.0))
            p_chg = pinfo.get("day_change_pct", 0.0) or 0.0
            p_pe = pinfo.get("pe_ratio", 0.0) or 0.0
            p_cap = pinfo.get("market_cap", 0.0) or 0.0
            
            p_chg_sign = "+" if p_chg >= 0 else ""
            badge_style = "background-color: rgba(0, 230, 118, 0.15); color: #00E676; padding: 4px 8px; border-radius: 4px; font-weight: 700; font-family: 'JetBrains Mono', monospace;" if p_chg >= 0 else "background-color: rgba(255, 23, 68, 0.15); color: #FF1744; padding: 4px 8px; border-radius: 4px; font-weight: 700; font-family: 'JetBrains Mono', monospace;"
            
            is_active = (psym == sym)
            td_bg = "background-color: rgba(0, 230, 118, 0.08);" if is_active else ""
            border_left = "border-left: 4px solid #00E676;" if is_active else ""
            font_weight = "font-weight: 800;" if is_active else "font-weight: 600;"
            
            st.markdown(f"""
                <tr style="border-bottom: 1px solid #1E2433;">
                    <td style="padding: 12px 14px; {td_bg} {border_left} color:#58A6FF; {font_weight}">{psym}</td>
                    <td style="padding: 12px 14px; {td_bg} color:#FFFFFF; {font_weight}">{pinfo.get('long_name', psym)}</td>
                    <td style="padding: 12px 14px; {td_bg} text-align:right; color:#FFFFFF; {font_weight} font-family:'JetBrains Mono', monospace;">${p_close:.2f}</td>
                    <td style="padding: 12px 14px; {td_bg} text-align:right;"><span style="{badge_style}">{p_chg_sign}{p_chg:.2f}%</span></td>
                    <td style="padding: 12px 14px; {td_bg} text-align:right; color:#FFFFFF; {font_weight} font-family:'JetBrains Mono', monospace;">{f"{p_pe:.1f}x" if p_pe > 0 else "N/A"}</td>
                    <td style="padding: 12px 14px; {td_bg} text-align:right; color:#FFFFFF; {font_weight} font-family:'JetBrains Mono', monospace;">{format_market_cap(p_cap)}</td>
                </tr>
            """, unsafe_allow_html=True)
        st.markdown("</tbody></table></div>", unsafe_allow_html=True)

        pats = detect_patterns(df_prices)
        if pats:
            st.markdown("<div class='fintech-card'>", unsafe_allow_html=True)
            st.markdown("<div style='font-size:10px; color:#8A94A6; font-weight:600; text-transform:uppercase; margin-bottom:4px;'>Detected Formations</div>", unsafe_allow_html=True)
            for p in pats:
                st.markdown(f"<span style='color:#00C805; font-weight:700; margin-right:12px;'>{p}</span>", unsafe_allow_html=True)
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
    color = "#00C805" if npl >= 0 else "#FF3B30"
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
        <div class="fin-readout" style="color:#FFFFFF;">${cash:,.2f}</div>
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
                <tr style="border-bottom:1px solid #1E2433; color:#8A94A6; font-size:11px; text-transform:uppercase; text-align:left;">
                    <th style="padding: 10px 12px; background-color: #11151F !important;">Symbol</th>
                    <th style="padding: 10px 12px; text-align:right; background-color: #11151F !important;">Last</th>
                    <th style="padding: 10px 12px; text-align:right; background-color: #11151F !important;">Change</th>
                </tr>
            </thead>
            <tbody>
        """, unsafe_allow_html=True)
        for tk in watchlist_tickers:
            info = get_ticker_info(tk)
            chg = info.get("day_change_pct", 0.0) or 0.0
            price = wl_prices.get(tk, info.get("previous_close", 150.0))
            sign_chg = "+" if chg >= 0 else ""
            badge_style = "background-color: rgba(0, 230, 118, 0.08); color: #00E676; border: 1px solid rgba(0, 230, 118, 0.2); padding: 3px 6px; border-radius: 4px; font-weight: 700; font-family: 'JetBrains Mono', monospace;" if chg >= 0 else "background-color: rgba(255, 23, 68, 0.08); color: #FF1744; border: 1px solid rgba(255, 23, 68, 0.2); padding: 3px 6px; border-radius: 4px; font-weight: 700; font-family: 'JetBrains Mono', monospace;"
            st.markdown(f"""
                <tr style="border-bottom: 1px solid #1E2433;">
                    <td style="padding: 10px 12px; font-weight:700;"><a href="/?tab=TRADE_DESK&ticker={tk}" target="_self" style="color:#58A6FF; text-decoration:none;">{tk}</a></td>
                    <td style="padding: 10px 12px; text-align:right; font-weight:700; color:#FFFFFF; font-family:'JetBrains Mono', monospace;">${price:.2f}</td>
                    <td style="padding: 10px 12px; text-align:right;"><span style="{badge_style}">{sign_chg}{chg:.2f}%</span></td>
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
                    <tr style="border-bottom:1px solid #1E2433; color:#8A94A6; font-size:10px; text-transform:uppercase;">
                        <th style="padding: 8px 10px; text-align:left; background-color: #11151F !important;">Sym</th>
                        <th style="padding: 8px 10px; text-align:right; background-color: #11151F !important;">Shares</th>
                        <th style="padding: 8px 10px; text-align:right; background-color: #11151F !important;">Value</th>
                        <th style="padding: 8px 10px; text-align:right; background-color: #11151F !important;">Return</th>
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
                    <tr style="border-bottom: 1px solid #1E2433;">
                        <td style="padding: 8px 10px; font-weight:700;"><a href="/?tab=TRADE_DESK&ticker={h_tk}" target="_self" style="color:#58A6FF; text-decoration:none;">{h_tk}</a></td>
                        <td style="padding: 8px 10px; text-align:right; color:#FFFFFF; font-family:'JetBrains Mono', monospace;">{h_shares}</td>
                        <td style="padding: 8px 10px; text-align:right; color:#FFFFFF; font-weight:700; font-family:'JetBrains Mono', monospace;">${h_val:,.2f}</td>
                        <td style="padding: 8px 10px; text-align:right; font-weight:700;" class="{h_cc}">{h_sign}{h_ret:.1f}%</td>
                    </tr>
                """, unsafe_allow_html=True)
            st.markdown("</tbody></table></div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='fintech-card'><div style='color:#8A94A6; font-size:11px; text-align:center; padding: 12px 0;'>No active positions held.</div></div>", unsafe_allow_html=True)
            
        # ── Balance Summary ──
        st.subheader("Balance Summary")
        st.markdown(f"""
        <div class="fintech-card" style="padding: 12px; font-variant-numeric: tabular-nums;">
            <div style="display:flex; justify-content:space-between; margin-bottom: 8px; font-size:12px;">
                <span style="color:#8A94A6;">Cash Balance:</span>
                <span style="color:#FFFFFF; font-weight:700; font-family:'JetBrains Mono', monospace;">${cash:,.2f}</span>
            </div>
            <div style="display:flex; justify-content:space-between; margin-bottom: 8px; font-size:12px;">
                <span style="color:#8A94A6;">Assets Value:</span>
                <span style="color:#FFFFFF; font-weight:700; font-family:'JetBrains Mono', monospace;">${hmv:,.2f}</span>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:12px; border-top:1px solid #1E2433; padding-top:8px; margin-top:8px;">
                <span style="color:#8A94A6; font-weight:700;">Buying Power:</span>
                <span style="color:#00E676; font-weight:800; font-family:'JetBrains Mono', monospace;">${cash:,.2f}</span>
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
            st.markdown("<div class='fintech-card'><div style='color:#8A94A6; font-size:12px;'>Insufficient stock history for advanced charts</div></div>", unsafe_allow_html=True)

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
        chg = info.get("day_change_pct", 0.0) or 0.0
        cc = "color-green" if chg >= 0 else "color-red"
        sign_chg = "+" if chg >= 0 else ""
        
        st.markdown(f"""
        <div class="fintech-card" style="padding: 12px; margin-bottom: 6px;">
            <div style="font-size:11px; color:#8A94A6; font-weight:700; text-transform:uppercase;">Quote Details / {ttk}</div>
            <div style="font-size:24px; font-weight:800; color:#FFFFFF; margin-top:4px; font-variant-numeric: tabular-nums;">${sp:.2f}</div>
            <div class="{cc}" style="font-size:12px; font-weight:700; margin-top:2px;">{sign_chg}{chg:.2f}%</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Order Book (L2) Mock Grid
        st.markdown("""
        <div class="fintech-card" style="padding: 10px; margin-bottom: 6px;">
            <div style="font-size:10px; color:#8A94A6; font-weight:700; text-transform:uppercase; margin-bottom:6px;">Order Book (L2)</div>
            <table style="width:100%; border-collapse:collapse; font-size:11px; font-variant-numeric: tabular-nums; font-family:'Inter', -apple-system, sans-serif;">
                <thead>
                    <tr style="border-bottom:1px solid #1E2433; color:#8A94A6;">
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
                    <tr style="border-bottom: 1px solid #1E2433;">
                        <td style="color:#00C805; font-weight:600; text-align:left; padding: 4px 0;">{bs}</td>
                        <td style="color:#FFFFFF; font-weight:600; text-align:center; padding: 4px 0;">${bp:.2f} | ${ap:.2f}</td>
                        <td style="color:#FF3B30; font-weight:600; text-align:right; padding: 4px 0;">{as_sz}</td>
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
            <div style="font-size:10px; color:#8A94A6; font-weight:700; text-transform:uppercase; margin-bottom:6px;">Time & Sales</div>
            <table style="width:100%; border-collapse:collapse; font-size:11px; font-variant-numeric: tabular-nums; font-family:'Inter', -apple-system, sans-serif;">
                <thead>
                    <tr style="border-bottom:1px solid #1E2433; color:#8A94A6;">
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
                    <tr style="border-bottom: 1px solid #1E2433;">
                        <td style="color:#8A94A6; text-align:left; padding: 4px 0;">{p_time}</td>
                        <td class="{cc_col}" style="font-weight:600; text-align:right; padding: 4px 0;">${p_price:.2f}</td>
                        <td style="color:#FFFFFF; text-align:right; padding: 4px 0;">{p_sz}</td>
                        <td style="color:#8A94A6; text-align:right; padding: 4px 0;">{p_exch}</td>
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
        
        fp = go.Figure(data=[go.Pie(labels=labels, values=vals, hole=.4, marker=dict(colors=['#161B26', '#00C805', '#58A6FF', '#FF3B30', '#D4D4D8', '#8B949E']))])
        fp.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color="#8A94A6", family="'Inter', -apple-system, sans-serif", size=11),
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
                    <tr style="border-bottom:1px solid #1E2433; color:#8A94A6; font-size:10px; text-transform:uppercase;">
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
                    <tr style="border-bottom: 1px solid #1E2433;">
                        <td style="padding: 6px 8px; color:#8A94A6;">{tx_time}</td>
                        <td style="padding: 6px 8px; text-align:center; font-weight:700;" class="{tx_cc}">{tx_type}</td>
                        <td style="padding: 6px 8px; font-weight:700; color:#FFFFFF;">{tx['ticker']}</td>
                        <td style="padding: 6px 8px; text-align:right; color:#FFFFFF; font-weight:700;">${tx['total']:,.2f}</td>
                    </tr>
                """, unsafe_allow_html=True)
            st.markdown("</tbody></table></div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='fintech-card'><div style='color:#8A94A6; font-size:11px; text-align:center; padding: 12px 0;'>No orders executed yet.</div></div>", unsafe_allow_html=True)

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
            <div style="font-size:13px; font-weight:600; color:#00C805; margin-bottom:6px;">BULLISH CANDLE</div>
            <p style="font-size:12px; color:#C9D1D9;">Stock closed higher than it opened.</p>
            <ul style="font-size:12px; color:#C9D1D9; padding-left: 14px;">
                <li><strong>Upper Wick:</strong> Highest price achieved</li>
                <li><strong>Body Top:</strong> Closing price</li>
                <li><strong>Body Bottom:</strong> Opening price</li>
                <li><strong>Lower Wick:</strong> Lowest price achieved</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        c2.markdown("""
        <div class="fintech-card">
            <div style="font-size:13px; font-weight:600; color:#FF3B30; margin-bottom:6px;">BEARISH CANDLE</div>
            <p style="font-size:12px; color:#C9D1D9;">Stock closed lower than it opened.</p>
            <ul style="font-size:12px; color:#C9D1D9; padding-left: 14px;">
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
            <div style="font-size:13px; font-weight:600; color:#8A94A6; margin-bottom:6px;">DOJI INDECISION</div>
            <p style="font-size:12px; color:#C9D1D9;">Open and close nearly identical. Signals market indecision.</p>
            <ul style="font-size:12px; color:#C9D1D9; padding-left: 14px;">
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
            increasing=dict(line=dict(color="#00C805", width=3.5), fillcolor="#00C805"),
            decreasing=dict(line=dict(color="#FF3B30", width=3.5), fillcolor="#FF3B30")
        )])
        fig_anatomy.update_layout(
            title=dict(text="Interactive Candlestick Schematics (Hover to inspect prices)", font=dict(size=12, color="#8A94A6")),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(t=35, b=10, l=10, r=10), height=320,
            xaxis=dict(showgrid=True, gridcolor="#1E2433", showline=True, linecolor="#2A3142", rangeslider=dict(visible=False)),
            yaxis=dict(showgrid=True, gridcolor="#1E2433", showline=True, linecolor="#2A3142", tickprefix="$")
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
            st.markdown(f'<div class="fintech-card {hhl}"><div style="font-size:10px; color:#00C805; font-weight:700;">SINGLE CANDLE</div><div style="font-size:13px; font-weight:600; color:#F4F4F5; margin:2px 0;">Hammer</div><p style="font-size:12px; color:#C9D1D9;">Small body, long lower wick. Buyers surged back.</p><div style="font-size:10px; color:#8A94A6;">Wait for next candle above the high.</div></div>', unsafe_allow_html=True)
            ehl = "card-highlighted" if highlighted == "Bullish Engulfing" else ""
            st.markdown(f'<div class="fintech-card {ehl}"><div style="font-size:10px; color:#00C805; font-weight:700;">DOUBLE CANDLE</div><div style="font-size:13px; font-weight:600; color:#F4F4F5; margin:2px 0;">Bullish Engulfing</div><p style="font-size:12px; color:#C9D1D9;">Green candle engulfs prior red candle.</p><div style="font-size:10px; color:#8A94A6;">Look for high volume confirmation.</div></div>', unsafe_allow_html=True)
            dbhl = "card-highlighted" if highlighted == "Double Bottom" else ""
            st.markdown(f'<div class="fintech-card {dbhl}"><div style="font-size:10px; color:#00C805; font-weight:700;">MULTI-DAY</div><div style="font-size:13px; font-weight:600; color:#F4F4F5; margin:2px 0;">Double Bottom (W)</div><p style="font-size:12px; color:#C9D1D9;">Two bounces off support, forming W shape. Bullish reversal.</p><div style="font-size:10px; color:#8A94A6;">Buy when price breaks above the neckline.</div></div>', unsafe_allow_html=True)
            
            # W Pattern Plotly
            w_x = [1, 2, 3, 4, 5, 6, 7]
            w_y = [10, 5, 8, 4.8, 9, 7.5, 12]
            fig_w = go.Figure()
            fig_w.add_trace(go.Scatter(x=w_x, y=w_y, mode="lines+markers", line=dict(color="#00C805", width=3), name="Double Bottom (W)", showlegend=False))
            fig_w.add_shape(type="line", x0=1, y0=10, x1=7, y1=10, line=dict(color="#8A94A6", dash="dash"))
            fig_w.update_layout(
                title=dict(text="Double Bottom Schema (Neckline Breakout)", font=dict(size=11, color="#8A94A6")),
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
            st.markdown(f'<div class="fintech-card {sshl}"><div style="font-size:10px; color:#FF3B30; font-weight:700;">SINGLE CANDLE</div><div style="font-size:13px; font-weight:600; color:#F4F4F5; margin:2px 0;">Shooting Star</div><p style="font-size:12px; color:#C9D1D9;">Small body, long upper wick. Sellers surged back.</p><div style="font-size:10px; color:#8A94A6;">Wait for next candle below the low.</div></div>', unsafe_allow_html=True)
            behl = "card-highlighted" if highlighted == "Bearish Engulfing" else ""
            st.markdown(f'<div class="fintech-card {behl}"><div style="font-size:10px; color:#FF3B30; font-weight:700;">DOUBLE CANDLE</div><div style="font-size:13px; font-weight:600; color:#F4F4F5; margin:2px 0;">Bearish Engulfing</div><p style="font-size:12px; color:#C9D1D9;">Red candle engulfs prior green candle.</p><div style="font-size:10px; color:#8A94A6;">Check for high seller volume.</div></div>', unsafe_allow_html=True)
            dthl = "card-highlighted" if highlighted == "Double Top" else ""
            st.markdown(f'<div class="fintech-card {dthl}"><div style="font-size:10px; color:#FF3B30; font-weight:700;">MULTI-DAY</div><div style="font-size:13px; font-weight:600; color:#F4F4F5; margin:2px 0;">Double Top (M)</div><p style="font-size:12px; color:#C9D1D9;">Two failed peaks at resistance, forming M shape. Bearish reversal.</p><div style="font-size:10px; color:#8A94A6;">Sell when price breaks below the neckline.</div></div>', unsafe_allow_html=True)
            
            # M Pattern Plotly
            m_x = [1, 2, 3, 4, 5, 6, 7]
            m_y = [5, 10, 7, 10.2, 6.8, 5, 3]
            fig_m = go.Figure()
            fig_m.add_trace(go.Scatter(x=m_x, y=m_y, mode="lines+markers", line=dict(color="#FF3B30", width=3), name="Double Top (M)", showlegend=False))
            fig_m.add_shape(type="line", x0=1, y0=7, x1=7, y1=7, line=dict(color="#8A94A6", dash="dash"))
            fig_m.update_layout(
                title=dict(text="Double Top Schema (Neckline Breakdown)", font=dict(size=11, color="#8A94A6")),
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
                    <tr style="border-bottom:1px solid #1E2433; color:#8A94A6; font-size:11px; text-transform:uppercase; text-align:left;">
                        <th style="padding-bottom:6px;">Type</th>
                        <th style="padding-bottom:6px;">Pattern</th>
                        <th style="padding-bottom:6px;">Description</th>
                        <th style="padding-bottom:6px;">Confirmation</th>
                    </tr>
                </thead>
                <tbody>
                    <tr style="border-bottom:1px solid #1E2433;">
                        <td style="padding:6px 0; color:#00E676; font-weight:600;">Bullish Continuation</td>
                        <td>Bullish Flag</td>
                        <td>Downward channel after sharp rise</td>
                        <td>Buy above top line</td>
                    </tr>
                    <tr style="border-bottom:1px solid #1E2433;">
                        <td style="padding:6px 0; color:#00E676; font-weight:600;">Bullish Continuation</td>
                        <td>Pennant</td>
                        <td>Triangle consolidation after rise</td>
                        <td>Buy above triangle</td>
                    </tr>
                    <tr style="border-bottom:1px solid #1E2433;">
                        <td style="padding:6px 0; color:#00E676; font-weight:600;">Bullish Reversal</td>
                        <td>Cup and Handle</td>
                        <td>U-bottom followed by small dip</td>
                        <td>Buy above handle top</td>
                    </tr>
                    <tr style="border-bottom:1px solid #1E2433;">
                        <td style="padding:6px 0; color:#FF1744; font-weight:600;">Bearish Continuation</td>
                        <td>Bearish Flag</td>
                        <td>Upward channel after sharp fall</td>
                        <td>Sell below bottom line</td>
                    </tr>
                    <tr style="border-bottom:1px solid #1E2433;">
                        <td style="padding:6px 0; color:#FF1744; font-weight:600;">Bearish Reversal</td>
                        <td>Double Top (M)</td>
                        <td>Two peaks at structural ceiling</td>
                        <td>Sell below neckline</td>
                    </tr>
                    <tr>
                        <td style="padding:6px 0; color:#00E676; font-weight:600;">Bullish Reversal</td>
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
    <div style="font-size:14px; font-weight:600; color:#FFFFFF; margin-bottom:8px;">RSI (Relative Strength Index)</div>
    <p style="color:#C9D1D9; line-height:1.4; margin-bottom:12px;">Measures momentum on a 0-100 scale. Readings above 70 indicate an overbought state (potential pullback), while values below 30 suggest an oversold condition (potential bounce).</p>
    <div style="font-size:14px; font-weight:600; color:#FFFFFF; margin-bottom:8px;">SMA (Simple Moving Average)</div>
    <p style="color:#C9D1D9; line-height:1.4; margin-bottom:12px;">Smooths out price volatility by calculating average closing levels over specific intervals. The 20-day average tracks short-term momentum, the 60-day monitors medium-term trend, and the 200-day defines the structural long-term anchor.</p>
    <div style="font-size:14px; font-weight:600; color:#FFFFFF; margin-bottom:8px;">Volatility Cap Risk Calculator</div>
    <p style="color:#C9D1D9; line-height:1.4; margin-bottom:12px;">Applies position sizing logic capped at exactly 25% of total virtual equity. Formulated as: <strong>min(25%, TargetRisk / Volatility x 100)</strong>. This forces smaller position sizes on highly volatile assets to safeguard overall capital.</p>
    <div style="font-size:14px; font-weight:600; color:#FFFFFF; margin-bottom:8px;">Support & Resistance Floors</div>
    <p style="color:#C9D1D9; line-height:1.4; margin-bottom:12px;">Support marks the historical floor where buyers emerge to halt price declines. Resistance marks the historical ceiling where sellers supply stock to prevent further advances. Computed from the 20-day high and low parameters.</p>
    <div style="font-size:14px; font-weight:600; color:#FFFFFF; margin-bottom:8px;">MACD (Moving Average Convergence Divergence)</div>
    <p style="color:#C9D1D9; line-height:1.4;">A trend-following momentum indicator showing the relationship between two moving averages (12 EMA and 26 EMA) of an asset's price. When the MACD line crosses above the Signal line, it indicates bullish momentum; when it crosses below, bearish momentum.</p>
</div>
""", unsafe_allow_html=True)
