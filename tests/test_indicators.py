"""Tests for indicators.py.

The most valuable cases here are the ones pinning the *honest failure*
behaviour. An indicator that returns a plausible number when it has no data is
worse than one that raises, because nothing downstream can tell the difference.
"""

import numpy as np
import pandas as pd
import pytest

import indicators


# ==============================================================================
# Reference implementation
# ==============================================================================
# Copied verbatim from the version that lived inline in app.py, so the
# vectorized replacement can be pinned against it. If this ever diverges, the
# rewrite changed a published number and that needs to be a deliberate choice.


def _legacy_rsi(close_prices, period=14):
    P = list(close_prices)
    if len(P) < period + 1:
        return 50.0
    gains, losses = [], []
    for idx in range(1, len(P)):
        diff = P[idx] - P[idx - 1]
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


@pytest.fixture
def walk():
    rng = np.random.default_rng(7)
    return pd.Series(100 + np.cumsum(rng.normal(0, 1.2, 300)))


# ==============================================================================
# RSI
# ==============================================================================


@pytest.mark.parametrize("n", [20, 30, 60, 250, 700])
def test_rsi_matches_legacy_implementation(n):
    rng = np.random.default_rng(n)
    px = pd.Series(100 + np.cumsum(rng.normal(0, 1.2, n)))
    assert indicators.rsi(px) == pytest.approx(_legacy_rsi(px), abs=1e-9)


def test_rsi_series_matches_legacy_at_every_bar(walk):
    """The chart used to call the scalar RSI on each expanding slice.

    rsi_series must reproduce that curve exactly, or the rewrite silently
    redraws every RSI panel in the app.
    """
    series = indicators.rsi_series(walk)
    for i in range(20, len(walk)):
        assert series.iloc[i] == pytest.approx(_legacy_rsi(walk.iloc[: i + 1]), abs=1e-9)


def test_rsi_returns_none_on_insufficient_history():
    # The legacy version returned 50.0 here - a perfectly neutral reading,
    # indistinguishable from a real measurement.
    assert indicators.rsi(pd.Series([1.0, 2.0, 3.0])) is None
    assert indicators.rsi(pd.Series([], dtype=float)) is None


def test_rsi_is_100_when_there_are_no_losses():
    assert indicators.rsi(pd.Series(np.arange(1.0, 40.0))) == pytest.approx(100.0)


def test_rsi_is_zero_when_there_are_no_gains():
    assert indicators.rsi(pd.Series(np.arange(40.0, 1.0, -1.0))) == pytest.approx(0.0)


def test_rsi_stays_in_bounds(walk):
    series = indicators.rsi_series(walk).dropna()
    assert len(series) > 0
    assert series.between(0.0, 100.0).all()


def test_rsi_series_is_nan_before_the_seed_window(walk):
    series = indicators.rsi_series(walk, period=14)
    assert series.iloc[:14].isna().all()
    assert not pd.isna(series.iloc[14])


# ==============================================================================
# MACD / EMA / volatility
# ==============================================================================


def test_macd_returns_none_below_slow_period():
    assert indicators.macd(pd.Series(range(10))) is None


def test_macd_histogram_is_line_minus_signal(walk):
    line, signal, hist = indicators.macd(walk)
    assert hist == pytest.approx(line - signal, abs=1e-9)


def test_macd_of_a_flat_series_is_zero():
    flat = pd.Series([50.0] * 100)
    line, signal, hist = indicators.macd(flat)
    assert line == pytest.approx(0.0, abs=1e-9)
    assert hist == pytest.approx(0.0, abs=1e-9)


def test_ema_of_constant_series_is_that_constant():
    assert indicators.ema(pd.Series([7.0] * 50), 12).iloc[-1] == pytest.approx(7.0)


def test_annualized_volatility_returns_none_when_unmeasurable():
    # Previously 0.0 with level "Low" - failure rendered as genuine calm.
    assert indicators.annualized_volatility(pd.Series([1.0])) is None
    assert indicators.annualized_volatility(pd.Series([], dtype=float)) is None


def test_annualized_volatility_of_flat_series_is_zero():
    assert indicators.annualized_volatility(pd.Series([10.0] * 60)) == pytest.approx(0.0)


def test_higher_variance_gives_higher_volatility():
    rng = np.random.default_rng(3)
    calm = pd.Series(100 + np.cumsum(rng.normal(0, 0.2, 200)))
    wild = pd.Series(100 + np.cumsum(rng.normal(0, 3.0, 200)))
    assert indicators.annualized_volatility(wild) > indicators.annualized_volatility(calm)


# ==============================================================================
# Patterns
# ==============================================================================


def _bars(rows):
    return pd.DataFrame(rows, columns=["Open", "High", "Low", "Close"])


def test_detect_patterns_needs_data():
    assert indicators.detect_patterns(pd.DataFrame()) == []
    assert indicators.detect_patterns(_bars([[1, 2, 0, 1]])) == []


def test_detect_patterns_tolerates_missing_columns():
    assert indicators.detect_patterns(pd.DataFrame({"Close": [1, 2, 3, 4]})) == []


def test_doji_is_detected():
    bars = _bars([[10, 11, 9, 10], [10, 11, 9, 10], [10, 12, 8, 10.05]])
    assert "Doji" in indicators.detect_patterns(bars)


def test_bullish_engulfing_is_detected():
    # previous bar down (open 11 -> close 10), current bar up and engulfing it
    bars = _bars([[10, 11, 9, 10], [11, 11.2, 9.8, 10.0], [9.5, 12.0, 9.4, 11.5]])
    assert "Bullish Engulfing" in indicators.detect_patterns(bars)


def test_bearish_engulfing_is_detected():
    bars = _bars([[10, 11, 9, 10], [10.0, 11.2, 9.8, 11.0], [11.5, 11.6, 9.4, 9.5]])
    assert "Bearish Engulfing" in indicators.detect_patterns(bars)


def test_engulfing_patterns_are_mutually_exclusive():
    rng = np.random.default_rng(11)
    for _ in range(50):
        data = 100 + np.cumsum(rng.normal(0, 1.0, (25, 4)), axis=0)
        frame = _bars([[o, max(o, c) + 0.5, min(o, c) - 0.5, c]
                       for o, _, _, c in data])
        found = indicators.detect_patterns(frame)
        assert not ("Bullish Engulfing" in found and "Bearish Engulfing" in found)


# ==============================================================================
# Channel
# ==============================================================================


def test_classify_channel_returns_none_without_enough_history():
    # None rather than "Sideways", so unknown is never mistaken for flat.
    assert indicators.classify_channel(pd.DataFrame({"Close": [1, 2, 3]})) is None


def test_classify_channel_detects_a_rising_trend():
    frame = pd.DataFrame({"Close": np.linspace(100, 200, 120)})
    assert indicators.classify_channel(frame) == "Ascending"


def test_classify_channel_detects_a_falling_trend():
    frame = pd.DataFrame({"Close": np.linspace(200, 100, 120)})
    assert indicators.classify_channel(frame) == "Descending"


def test_classify_channel_detects_flat():
    frame = pd.DataFrame({"Close": [100.0] * 120})
    assert indicators.classify_channel(frame) == "Sideways"
