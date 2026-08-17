"""
Market data fetching, with one rule: **never invent a number.**

Every function here either returns measured data or raises
:class:`DataUnavailable`. Nothing returns a plausible substitute, because a
substitute is indistinguishable from a measurement once it reaches the UI, and
in a financial tool that is the difference between "we don't know" and a lie.

This replaces the fetchers that previously lived in ``app.py``, which on failure
fell back to:

* fundamentals invented wholesale - market cap 250e9, P/E 24.5, EPS 4.5 - and a
  day-change percentage *derived from the character-sum of the ticker symbol*;
* a full table of synthetic gainers and losers built from the same seed
  whenever fewer than five real records came back;
* a hardcoded futures price table.

Two further conventions:

**A missing field is ``None``, not ``0.0``.** The old code coerced every absent
field to zero, so an unknown P/E rendered as a real P/E of 0.00 and an unknown
beta as a beta of 0.00. Optional fields are typed ``Optional[float]`` and the
UI is expected to render ``None`` as "unavailable".

**Windows are labelled by what was actually measured.** The scanner previously
downloaded 65 days of history, compared the last close against the high of that
window, and the UI labelled the result "52W HIGH". The window length is now
carried on the result so the caller can label it truthfully.

Caching is deliberately *not* applied here - it belongs to the Streamlit layer,
which wraps these in ``@st.cache_data``. Keeping this module free of Streamlit
is what allows the workflow tools and the tests to call it directly.
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import pandas as pd
import requests
import yfinance as yf

__all__ = [
    "DataUnavailable",
    "TickerSnapshot",
    "ScannerResult",
    "fetch_ticker_info",
    "fetch_rss_news",
    "fetch_scanner_universe",
    "fetch_price_history",
]


class DataUnavailable(Exception):
    """Raised when data could not be obtained.

    Carries enough context for the UI to say *what* failed and *where it was
    asked from*, rather than a bare "no data".
    """

    def __init__(self, what: str, source: str, detail: str = ""):
        self.what = what
        self.source = source
        self.detail = detail
        message = f"{what} unavailable from {source}"
        if detail:
            message = f"{message}: {detail}"
        super().__init__(message)


def _opt_float(value) -> Optional[float]:
    """Coerce to float, mapping absent/non-numeric to ``None`` rather than 0.0."""
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(out) else out


# ==============================================================================
# FUNDAMENTALS / QUOTE SNAPSHOT
# ==============================================================================


@dataclass
class TickerSnapshot:
    """A point-in-time quote and fundamentals snapshot.

    Every numeric field is optional. ``None`` means the provider did not supply
    it, which is a different statement from zero.
    """

    symbol: str
    source: str
    fetched_at: float
    long_name: Optional[str] = None
    previous_close: Optional[float] = None
    open: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[float] = None
    avg_volume: Optional[float] = None
    market_cap: Optional[float] = None
    beta: Optional[float] = None
    pe_ratio: Optional[float] = None
    eps: Optional[float] = None
    day_low: Optional[float] = None
    day_high: Optional[float] = None
    fifty_two_low: Optional[float] = None
    fifty_two_high: Optional[float] = None
    day_change_pct: Optional[float] = None
    sector: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "symbol": self.symbol,
            "source": self.source,
            "fetched_at": self.fetched_at,
            "long_name": self.long_name,
            "previous_close": self.previous_close,
            "open": self.open,
            "bid": self.bid,
            "ask": self.ask,
            "volume": self.volume,
            "avg_volume": self.avg_volume,
            "market_cap": self.market_cap,
            "beta": self.beta,
            "pe_ratio": self.pe_ratio,
            "eps": self.eps,
            "day_low": self.day_low,
            "day_high": self.day_high,
            "fifty_two_low": self.fifty_two_low,
            "fifty_two_high": self.fifty_two_high,
            "day_change_pct": self.day_change_pct,
            "sector": self.sector,
        }


def fetch_ticker_info(symbol: str) -> TickerSnapshot:
    """Quote and fundamentals for *symbol*.

    Raises :class:`DataUnavailable` if the provider call fails or returns
    nothing usable. Individual fields the provider omits come back as ``None``.
    """
    symbol = (symbol or "").strip().upper()
    if not symbol:
        raise DataUnavailable("ticker info", "yfinance", "no symbol given")

    try:
        info = yf.Ticker(symbol).info or {}
    except Exception as exc:  # noqa: BLE001 - provider raises many types
        raise DataUnavailable("ticker info", "yfinance", str(exc)) from exc

    # yfinance returns a sparse dict for unknown symbols rather than raising, so
    # an empty-ish payload has to be treated as a failure explicitly.
    if not info or len(info) < 3:
        raise DataUnavailable("ticker info", "yfinance", f"no data for {symbol}")

    previous_close = _opt_float(
        info.get("previousClose") or info.get("regularMarketPreviousClose")
    )
    current = _opt_float(
        info.get("currentPrice") or info.get("regularMarketPrice") or info.get("open")
    )

    change_pct = _opt_float(info.get("regularMarketChangePercent"))
    if change_pct is None and previous_close and current and previous_close > 0:
        change_pct = ((current - previous_close) / previous_close) * 100.0
    # If neither the provider nor arithmetic can produce it, it stays None.
    # The previous implementation fabricated it from sum(ord(c) for c in symbol).

    return TickerSnapshot(
        symbol=symbol,
        source="yfinance",
        fetched_at=time.time(),
        long_name=info.get("longName") or info.get("shortName") or None,
        previous_close=previous_close,
        open=_opt_float(info.get("open")),
        bid=_opt_float(info.get("bid")),
        ask=_opt_float(info.get("ask")),
        volume=_opt_float(info.get("volume")),
        avg_volume=_opt_float(info.get("averageVolume")),
        market_cap=_opt_float(info.get("marketCap")),
        beta=_opt_float(info.get("beta")),
        pe_ratio=_opt_float(info.get("trailingPE")),
        eps=_opt_float(info.get("trailingEps")),
        day_low=_opt_float(info.get("dayLow")),
        day_high=_opt_float(info.get("dayHigh")),
        fifty_two_low=_opt_float(info.get("fiftyTwoWeekLow")),
        fifty_two_high=_opt_float(info.get("fiftyTwoWeekHigh")),
        day_change_pct=change_pct,
        sector=info.get("sector") or None,
    )


# ==============================================================================
# NEWS
# ==============================================================================


def fetch_rss_news(symbol: str, limit: int = 12, timeout: float = 5.0) -> List[dict]:
    """Headlines for *symbol* from the Yahoo Finance RSS feed.

    An empty list is a legitimate outcome (a quiet ticker genuinely has no
    recent headlines); a transport or parse failure raises.
    """
    symbol = (symbol or "").strip().upper()
    if not symbol:
        raise DataUnavailable("news", "yahoo-rss", "no symbol given")

    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
    try:
        # requests, not urllib. urllib validates TLS against the *system* trust
        # store, which a python.org interpreter on macOS does not populate
        # unless the user runs Install Certificates.command - so every RSS fetch
        # died with CERTIFICATE_VERIFY_FAILED. The previous implementation
        # swallowed that in a bare except and returned [], so the News tab has
        # been silently empty rather than reporting a TLS problem. requests
        # ships certifi and verifies correctly out of the box.
        response = requests.get(
            url, timeout=timeout, headers={"User-Agent": "reverie-terminal/1.0"}
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except Exception as exc:  # noqa: BLE001
        raise DataUnavailable("news", "yahoo-rss", str(exc)) from exc

    items = []
    for item in root.findall(".//item")[:limit]:
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        items.append({
            "headline": title,
            "url": (item.findtext("link") or "").strip(),
            "published": (item.findtext("pubDate") or "").strip(),
            "source": "Yahoo Finance",
        })
    return items


# ==============================================================================
# PRICE HISTORY
# ==============================================================================


def fetch_price_history(
    symbols: Sequence[str], period: str = "1y", interval: str = "1d"
) -> pd.DataFrame:
    """Adjusted OHLCV history for one or many symbols, in a single request.

    Returns the raw yfinance frame (MultiIndex columns for multiple symbols).
    ``auto_adjust=True`` so long windows survive splits - without it, anything
    that split mid-window produces nonsense.
    """
    wanted = [s.strip().upper() for s in symbols if s and s.strip()]
    if not wanted:
        raise DataUnavailable("price history", "yfinance", "no symbols given")

    try:
        frame = yf.download(
            wanted,
            period=period,
            interval=interval,
            auto_adjust=True,
            group_by="ticker",
            progress=False,
            threads=True,
        )
    except Exception as exc:  # noqa: BLE001
        raise DataUnavailable("price history", "yfinance", str(exc)) from exc

    if frame is None or frame.empty:
        raise DataUnavailable(
            "price history", "yfinance", f"empty response for {', '.join(wanted)}"
        )
    return frame


# ==============================================================================
# SCANNERS
# ==============================================================================


@dataclass
class ScannerResult:
    """Ranked scanner output plus an explicit account of what was measured."""

    records: List[dict] = field(default_factory=list)
    requested: int = 0
    resolved: int = 0
    window_days: int = 0
    fetched_at: float = 0.0

    @property
    def coverage(self) -> float:
        return (self.resolved / self.requested) if self.requested else 0.0

    def top(self, key: str, n: int = 10, ascending: bool = False) -> List[dict]:
        return sorted(self.records, key=lambda r: r.get(key, 0.0),
                      reverse=not ascending)[:n]


def fetch_scanner_universe(
    symbols: Sequence[str], lookback_days: int = 65
) -> ScannerResult:
    """Per-symbol change, volume and window extremes across a universe.

    Raises if nothing at all resolved. Partial coverage is *reported* rather
    than topped up: the previous implementation replaced the entire record set
    with values seeded from ``sum(ord(c) for c in ticker)`` whenever fewer than
    five symbols came back, which produced a complete, plausible, entirely
    fictional set of market movers.

    ``window_days`` is carried on the result because the extremes are measured
    over the requested lookback, not over 52 weeks - the UI previously labelled
    a 65-day high as a "52W HIGH".
    """
    wanted = [s.strip().upper() for s in symbols if s and s.strip()]
    if not wanted:
        raise DataUnavailable("scanner", "yfinance", "no symbols given")

    frame = fetch_price_history(wanted, period=f"{lookback_days}d")

    records: List[dict] = []
    for symbol in wanted:
        try:
            if isinstance(frame.columns, pd.MultiIndex):
                if symbol not in frame.columns.get_level_values(0):
                    continue
                sub = frame[symbol].dropna()
            else:
                sub = frame.dropna()

            if sub.empty or len(sub) < 2:
                continue

            close = float(sub["Close"].iloc[-1])
            prev = float(sub["Close"].iloc[-2])
            if prev <= 0:
                continue

            volume = float(sub["Volume"].iloc[-1])
            avg_volume = float(sub["Volume"].mean())
            window_high = float(sub["High"].max())
            window_low = float(sub["Low"].min())

            records.append({
                "ticker": symbol,
                "close": close,
                "change": ((close - prev) / prev) * 100.0,
                "volume": volume,
                "avg_volume": avg_volume,
                "vol_ratio": volume / avg_volume if avg_volume > 0 else None,
                "window_high": window_high,
                "window_low": window_low,
                "at_window_high": close >= window_high * 0.98,
                "at_window_low": close <= window_low * 1.02,
                "observations": len(sub),
            })
        except (KeyError, IndexError, ValueError, TypeError):
            # One malformed symbol must not sink the scan, but it is counted as
            # unresolved rather than replaced.
            continue

    if not records:
        raise DataUnavailable(
            "scanner", "yfinance", f"no symbols resolved out of {len(wanted)}"
        )

    return ScannerResult(
        records=records,
        requested=len(wanted),
        resolved=len(records),
        window_days=lookback_days,
        fetched_at=time.time(),
    )
