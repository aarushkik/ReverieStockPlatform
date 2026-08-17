"""
Technical indicators and candlestick pattern detection.

Pure computation: no Streamlit, no network, no global state. Everything here
takes a DataFrame or Series and returns numbers, which makes it directly
unit-testable and safe to expose as workflow tools.

Two conventions that differ from the versions of these functions that
previously lived inline in ``app.py``:

1.  **Insufficient data returns ``None``, not a plausible number.** The old
    ``calculate_rsi`` returned ``50.0`` when it had fewer than ``period + 1``
    observations, and ``calculate_macd`` returned ``(0.0, 0.0, 0.0)`` under 26
    bars. Both are *valid readings* - RSI 50 is exactly neutral, MACD 0 is
    exactly no-momentum - so a caller could not tell a real measurement from a
    failed one, and the UI rendered the failure as a confident signal.

2.  **Series variants exist alongside scalar ones.** ``rsi_series`` computes the
    whole curve in one pass. The chart code previously called a scalar
    ``calculate_rsi`` inside a loop over expanding slices, which recomputed the
    entire history on every bar - O(n^2) for a value that is naturally O(n).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

__all__ = [
    "ema",
    "rsi_series",
    "rsi",
    "macd_series",
    "macd",
    "detect_patterns",
    "classify_channel",
    "annualized_volatility",
]


# ==============================================================================
# TREND
# ==============================================================================


def ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential moving average."""
    return series.ewm(span=period, adjust=False).mean()


def _wilder_smooth(values: np.ndarray, period: int) -> np.ndarray:
    """Wilder's smoothing, seeded with a simple mean of the first *period* values.

    Wilder's original formulation seeds the average with an SMA and then applies
    the recursive ``avg = (avg * (period - 1) + x) / period``. That is *not* the
    same as ``ewm(alpha=1/period, adjust=False)``, which seeds with the first
    observation - the two diverge for the first few dozen bars. Since the point
    of this function is to reproduce the existing indicator exactly while
    dropping the quadratic cost, the seeding is done explicitly.
    """
    out = np.full(values.shape, np.nan, dtype=float)
    if len(values) < period:
        return out

    avg = float(values[:period].mean())
    out[period - 1] = avg
    for i in range(period, len(values)):
        avg = (avg * (period - 1) + values[i]) / period
        out[i] = avg
    return out


def rsi_series(close: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index over the whole series.

    Returns a Series aligned to *close*, NaN until enough history exists.
    """
    close = pd.Series(close).astype(float)
    if len(close) < period + 1:
        return pd.Series(np.nan, index=close.index, dtype=float)

    delta = close.diff().iloc[1:]
    gains = delta.clip(lower=0.0).to_numpy(dtype=float)
    losses = (-delta.clip(upper=0.0)).to_numpy(dtype=float)

    avg_gain = _wilder_smooth(gains, period)
    avg_loss = _wilder_smooth(losses, period)

    with np.errstate(divide="ignore", invalid="ignore"):
        rs = np.divide(avg_gain, avg_loss)
        values = 100.0 - (100.0 / (1.0 + rs))

    # A window with no losses is RSI 100 by definition, not a division error.
    values = np.where((avg_loss == 0) & ~np.isnan(avg_gain), 100.0, values)

    out = np.full(len(close), np.nan, dtype=float)
    out[1:] = values
    return pd.Series(out, index=close.index, dtype=float)


def rsi(close: pd.Series, period: int = 14) -> Optional[float]:
    """Latest RSI reading, or ``None`` when there is not enough history."""
    series = rsi_series(close, period)
    if series.empty:
        return None
    last = series.iloc[-1]
    return None if pd.isna(last) else float(last)


def macd_series(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """MACD line, signal line and histogram as full series."""
    series = pd.Series(series).astype(float)
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    return macd_line, signal_line, macd_line - signal_line


def macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> Optional[Tuple[float, float, float]]:
    """Latest ``(macd, signal, histogram)``, or ``None`` without enough history."""
    series = pd.Series(series).astype(float)
    if len(series) < slow:
        return None
    line, sig, hist = macd_series(series, fast, slow, signal)
    return float(line.iloc[-1]), float(sig.iloc[-1]), float(hist.iloc[-1])


def annualized_volatility(
    close: pd.Series, lookback: int = 20, periods_per_year: int = 252
) -> Optional[float]:
    """Annualized volatility as a percentage, or ``None`` when unmeasurable.

    The previous implementation in ``analyzer.py`` returned ``0.0`` with a level
    of ``"Low"`` whenever it failed, which renders as *genuinely calm* - the
    most dangerous possible way for a volatility measure to fail.
    """
    close = pd.Series(close).astype(float).dropna()
    if len(close) < 3:
        return None
    returns = close.pct_change().dropna().tail(lookback)
    if len(returns) < 2:
        return None
    std = float(returns.std())
    if np.isnan(std):
        return None
    return std * np.sqrt(periods_per_year) * 100.0


# ==============================================================================
# PATTERNS
# ==============================================================================


def detect_patterns(df: pd.DataFrame) -> List[str]:
    """Candlestick and short-horizon chart patterns on the most recent bars.

    Requires columns Open/High/Low/Close. Returns an empty list when nothing is
    detected or there is too little data - an empty list is honest here, since
    "no pattern" is a real outcome.
    """
    required = {"Open", "High", "Low", "Close"}
    if df is None or df.empty or len(df) < 3 or not required.issubset(df.columns):
        return []

    last, prev = df.iloc[-1], df.iloc[-2]
    o, h, l, c = (float(last["Open"]), float(last["High"]),
                  float(last["Low"]), float(last["Close"]))
    prev_o, prev_c = float(prev["Open"]), float(prev["Close"])

    span = h - l
    body = abs(o - c)
    lower_wick = min(o, c) - l
    upper_wick = h - max(o, c)

    found: List[str] = []

    if span > 0 and (body / span) < 0.08:
        found.append("Doji")

    if body > 0 and span > 0:
        if lower_wick > 2 * body and body < 0.3 * span and upper_wick < 0.2 * span:
            found.append("Hammer")
        if upper_wick > 2 * body and body < 0.3 * span and lower_wick < 0.2 * span:
            found.append("Shooting Star")

    if prev_c < prev_o and c > o and o <= prev_c and c >= prev_o:
        found.append("Bullish Engulfing")
    elif prev_c > prev_o and c < o and o >= prev_c and c <= prev_o:
        found.append("Bearish Engulfing")

    if len(df) >= 20:
        highs = df["High"].tail(20)
        lows = df["Low"].tail(20)
        peak, trough = float(highs.max()), float(lows.min())

        near_peaks = highs[highs >= peak * 0.99]
        if len(near_peaks) >= 2 and near_peaks.index[0] != near_peaks.index[-1]:
            found.append("Double Top")

        near_troughs = lows[lows <= trough * 1.01]
        if len(near_troughs) >= 2 and near_troughs.index[0] != near_troughs.index[-1]:
            found.append("Double Bottom")

    return found


def classify_channel(df: pd.DataFrame) -> Optional[str]:
    """Coarse trend classification from the 20- and 60-day averages.

    Returns ``None`` rather than a label when there is not enough history, so a
    caller cannot mistake "unknown" for "sideways".
    """
    if df is None or len(df) < 60 or "Close" not in df.columns:
        return None

    sma20 = df["Close"].rolling(20).mean()
    sma60 = df["Close"].rolling(60).mean()
    if pd.isna(sma20.iloc[-1]) or pd.isna(sma60.iloc[-1]):
        return None

    short, long_ = float(sma20.iloc[-1]), float(sma60.iloc[-1])
    if long_ == 0:
        return None

    spread = (short - long_) / long_ * 100.0
    if spread > 2.0:
        return "Ascending"
    if spread < -2.0:
        return "Descending"
    return "Sideways"
