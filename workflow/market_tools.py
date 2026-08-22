"""
The concrete tools a workflow can call.

Each is a thin adapter over ``marketdata``, ``indicators`` or ``analyzer``. They
exist to give the engine a uniform, declarable surface - a name, a parameter
schema and a JSON-safe return - rather than to add behaviour. Any real logic
belongs in the module underneath, where it is testable on its own.

Importing this module registers the tools. ``workflow/__init__.py`` does that
once, so ``workflow.tools.REGISTRY`` is populated by the time anything asks.

Tools that need price history accept a ``history`` argument, which the engine
fills from an upstream step's artifact. That keeps a workflow to one download
instead of one per analytical step, without any tool reaching into a cache it
doesn't own.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

import indicators
import marketdata as md
import predictive_model
from analyzer import analyze_sentiment

from .tools import tool

__all__ = ["close_series"]


def close_series(history: Any, symbol: str = "") -> pd.Series:
    """Pull a Close series out of whatever shape the caller passed.

    Accepts a Series, a single-symbol OHLCV frame, or a multi-symbol yfinance
    frame with MultiIndex columns.
    """
    if history is None:
        raise ValueError("no price history supplied")
    if isinstance(history, pd.Series):
        return history.astype(float).dropna()
    if not isinstance(history, pd.DataFrame) or history.empty:
        raise ValueError("price history is empty")

    frame = history
    if isinstance(frame.columns, pd.MultiIndex):
        symbol = (symbol or "").upper()
        level0 = frame.columns.get_level_values(0)
        if symbol and symbol in level0:
            frame = frame[symbol]
        else:
            frame = frame[level0[0]]
    if "Close" not in frame.columns:
        raise ValueError("price history has no Close column")
    return frame["Close"].astype(float).dropna()


def _ohlcv(history: Any, symbol: str = "") -> pd.DataFrame:
    if isinstance(history, pd.DataFrame) and isinstance(history.columns, pd.MultiIndex):
        level0 = history.columns.get_level_values(0)
        symbol = (symbol or "").upper()
        return history[symbol] if symbol in level0 else history[level0[0]]
    return history


# ==============================================================================
# DATA
# ==============================================================================


@tool(
    "prices",
    "Daily OHLCV price history for a symbol.",
    {
        "symbol": {"type": "string", "required": True, "description": "Ticker symbol"},
        "period": {"type": "string", "required": False,
                   "description": "Lookback, e.g. 6mo, 1y, 3y"},
    },
    source="yfinance",
)
def _prices(symbol: str, period: str = "1y"):
    frame = md.fetch_price_history([symbol], period=period)
    ohlcv = _ohlcv(frame, symbol).dropna()
    if ohlcv.empty:
        raise md.DataUnavailable("price history", "yfinance", f"no rows for {symbol}")

    close = ohlcv["Close"].astype(float)
    first, last = float(close.iloc[0]), float(close.iloc[-1])

    summary: Dict[str, Any] = {
        "symbol": symbol.upper(),
        "period": period,
        "observations": int(len(close)),
        "last_close": last,
        "first_close": first,
        "period_change_pct": ((last - first) / first * 100.0) if first else None,
        "period_high": float(ohlcv["High"].max()),
        "period_low": float(ohlcv["Low"].min()),
        "last_volume": float(ohlcv["Volume"].iloc[-1]),
        "start": str(close.index[0].date()),
        "end": str(close.index[-1].date()),
    }
    # The frame rides along as an artifact so downstream steps reuse it.
    return summary, frame


@tool(
    "fundamentals",
    "Quote and fundamentals snapshot: price, market cap, P/E, EPS, beta, ranges.",
    {"symbol": {"type": "string", "required": True, "description": "Ticker symbol"}},
    source="yfinance",
)
def _fundamentals(symbol: str) -> Dict[str, Any]:
    return md.fetch_ticker_info(symbol).to_dict()


@tool(
    "news",
    "Recent headlines for a symbol.",
    {
        "symbol": {"type": "string", "required": True, "description": "Ticker symbol"},
        "limit": {"type": "number", "required": False, "description": "Max headlines"},
    },
    source="yahoo-rss",
)
def _news(symbol: str, limit: int = 10) -> Dict[str, Any]:
    items = md.fetch_rss_news(symbol, limit=int(limit))
    return {
        "symbol": symbol.upper(),
        "count": len(items),
        # Headlines are strings, so they never become citable facts; they are
        # context for the model, and the count is the measurable part.
        "headlines": [i["headline"] for i in items],
        "items": items,
    }


@tool(
    "scanner",
    "Rank a universe of symbols by daily change, volume and window extremes.",
    {
        "symbols": {"type": "array", "required": True, "description": "Ticker symbols"},
        "lookback_days": {"type": "number", "required": False,
                          "description": "Window length in calendar days"},
    },
    source="yfinance",
)
def _scanner(symbols: Sequence[str], lookback_days: int = 65) -> Dict[str, Any]:
    result = md.fetch_scanner_universe(symbols, lookback_days=int(lookback_days))
    return {
        "requested": result.requested,
        "resolved": result.resolved,
        "coverage_pct": round(result.coverage * 100.0, 2),
        "window_days": result.window_days,
        "top_gainers": result.top("change", 5),
        "top_losers": result.top("change", 5, ascending=True),
        "most_active": result.top("volume", 5),
    }


# ==============================================================================
# ANALYTICS
# ==============================================================================


@tool(
    "indicators",
    "Technical indicators: RSI, MACD, moving averages, annualized volatility.",
    {
        "symbol": {"type": "string", "required": True, "description": "Ticker symbol"},
        "history": {"type": "object", "required": False,
                    "description": "Price history from a prices step"},
    },
    source="computed",
)
def _indicators(symbol: str, history: Any = None) -> Dict[str, Any]:
    if history is None:
        history = md.fetch_price_history([symbol], period="1y")
    close = close_series(history, symbol)

    macd = indicators.macd(close)
    out: Dict[str, Any] = {
        "symbol": symbol.upper(),
        "observations": int(len(close)),
        "last_close": float(close.iloc[-1]),
        "rsi_14": indicators.rsi(close, 14),
        "sma_20": float(close.tail(20).mean()) if len(close) >= 20 else None,
        "sma_60": float(close.tail(60).mean()) if len(close) >= 60 else None,
        "sma_200": float(close.tail(200).mean()) if len(close) >= 200 else None,
        "volatility_pct": indicators.annualized_volatility(close),
        "trend": indicators.classify_channel(pd.DataFrame({"Close": close})),
    }
    # None rather than zeros when there is too little history - the caller can
    # tell "not measured" from "measured as zero".
    out["macd"] = macd[0] if macd else None
    out["macd_signal"] = macd[1] if macd else None
    out["macd_histogram"] = macd[2] if macd else None
    return out


@tool(
    "patterns",
    "Candlestick and short-horizon chart patterns on the most recent bars.",
    {
        "symbol": {"type": "string", "required": True, "description": "Ticker symbol"},
        "history": {"type": "object", "required": False,
                    "description": "Price history from a prices step"},
    },
    source="computed",
)
def _patterns(symbol: str, history: Any = None) -> Dict[str, Any]:
    if history is None:
        history = md.fetch_price_history([symbol], period="6mo")
    frame = _ohlcv(history, symbol).dropna()
    found: List[str] = indicators.detect_patterns(frame)
    return {"symbol": symbol.upper(), "pattern_count": len(found), "patterns": found}


@tool(
    "sentiment",
    "Lexicon sentiment score across a set of headlines.",
    {
        "headlines": {"type": "array", "required": False,
                      "description": "Headlines from a news step"},
        "symbol": {"type": "string", "required": False, "description": "Ticker symbol"},
    },
    source="computed",
)
def _sentiment(headlines: Optional[Sequence[str]] = None,
               symbol: str = "") -> Dict[str, Any]:
    if headlines is None:
        headlines = [i["headline"] for i in md.fetch_rss_news(symbol)]
    articles = [{"headline": h} for h in headlines]
    result = analyze_sentiment(articles)
    return {
        "symbol": symbol.upper() if symbol else "",
        "article_count": len(articles),
        "sentiment_score": result["score"],
        "sentiment_label": result["label"],
    }


@tool(
    "portfolio",
    "The signed-in user's current simulated positions.",
    {"positions": {"type": "object", "required": True,
                   "description": "Holdings supplied by the app"}},
    source="portfolio",
)
def _portfolio(positions: Dict[str, Any]) -> Dict[str, Any]:
    holdings = positions.get("holdings") or {}
    cash = float(positions.get("cash") or 0.0)
    return {
        "position_count": len(holdings),
        "cash": cash,
        "symbols": sorted(holdings),
        "holdings": holdings,
    }


@tool(
    "forecast",
    "Train a price-direction classifier on the symbol's own history and report "
    "its backtested accuracy.",
    {
        "symbol": {"type": "string", "required": True, "description": "Ticker symbol"},
        "history": {"type": "object", "required": False,
                    "description": "Price history from a prices step"},
    },
    source="predictive_model",
)
def _forecast(symbol: str, history: Any = None) -> Dict[str, Any]:
    """Wraps predictive_model.train_predictive_model.

    Raises when the model could not be trained, so the workflow records a
    failed step rather than a neutral-looking prediction. That matters more
    here than anywhere else in the registry: a fabricated forecast is the one
    output a reader is most likely to act on, and the *only* honest thing to
    say about an untrained model is that it was not trained.

    Note what does and does not become a citable fact. The backtested accuracy
    and sample counts are real measurements and belong in the ledger. The
    forward price path is a projection, not a measurement, so it is deliberately
    returned as a length rather than as a series of prices the model could cite
    as though they had been observed.
    """
    if history is None:
        history = md.fetch_price_history([symbol], period="2y")
    frame = _ohlcv(history, symbol).dropna()

    result = predictive_model.train_predictive_model(symbol.upper(), frame)
    if not result.get("success"):
        raise RuntimeError(
            f"model not trained: {result.get('reason', 'unknown reason')}")

    return {
        "symbol": result["symbol"],
        "direction": result["prediction"],
        "bullish_probability_pct": result["bullish_probability"],
        "confidence_pct": result["confidence_pct"],
        "backtest_accuracy_pct": result["backtest_accuracy_pct"],
        "samples_trained": result["samples_trained"],
        "samples_tested": result["samples_tested"],
        "top_features": [f.get("feature") for f in result.get("feature_importances", [])[:5]],
        "forecast_days": len(result.get("forecast", [])),
    }
