"""Tests for marketdata.py.

No network. Provider calls are monkeypatched, because the property under test
is *what this module does with what it gets back* - especially when it gets
back nothing. That is exactly the path the old code filled with invented
numbers.
"""

import pandas as pd
import pytest

import marketdata as md


# ==============================================================================
# Field coercion
# ==============================================================================


@pytest.mark.parametrize(
    "raw, expected",
    [(None, None), ("", None), ("n/a", None), (float("nan"), None),
     (0, 0.0), (0.0, 0.0), ("12.5", 12.5), (3, 3.0)],
)
def test_opt_float_maps_absent_to_none_but_keeps_real_zero(raw, expected):
    """A genuine zero must survive; an absent value must not become zero.

    The old code coerced every missing field with `or 0.0`, so an unknown P/E
    rendered as a real P/E of 0.00.
    """
    assert md._opt_float(raw) == expected


# ==============================================================================
# fetch_ticker_info
# ==============================================================================


class _FakeTicker:
    def __init__(self, info):
        self.info = info


def _patch_ticker(monkeypatch, info):
    monkeypatch.setattr(md.yf, "Ticker", lambda symbol: _FakeTicker(info))


def test_ticker_info_rejects_empty_symbol():
    with pytest.raises(md.DataUnavailable):
        md.fetch_ticker_info("")


def test_ticker_info_raises_when_provider_returns_nothing(monkeypatch):
    # yfinance returns a sparse dict for unknown symbols rather than raising,
    # so an empty-ish payload has to be treated as failure explicitly.
    _patch_ticker(monkeypatch, {})
    with pytest.raises(md.DataUnavailable):
        md.fetch_ticker_info("NOPE")


def test_ticker_info_raises_when_provider_throws(monkeypatch):
    def boom(symbol):
        raise RuntimeError("upstream 503")

    monkeypatch.setattr(md.yf, "Ticker", boom)
    with pytest.raises(md.DataUnavailable) as excinfo:
        md.fetch_ticker_info("AAPL")
    assert "503" in str(excinfo.value)


def test_ticker_info_never_invents_a_change_percentage(monkeypatch):
    """The old implementation derived this from sum(ord(c) for c in symbol)."""
    _patch_ticker(monkeypatch, {"longName": "Test Co", "currency": "USD",
                                "exchange": "NMS"})
    snap = md.fetch_ticker_info("AAPL")
    assert snap.day_change_pct is None
    assert snap.market_cap is None
    assert snap.pe_ratio is None


def test_ticker_info_derives_change_when_it_can(monkeypatch):
    _patch_ticker(monkeypatch, {"previousClose": 100.0, "currentPrice": 110.0,
                                "longName": "Test Co"})
    snap = md.fetch_ticker_info("AAPL")
    assert snap.day_change_pct == pytest.approx(10.0)


def test_ticker_info_prefers_the_providers_own_change(monkeypatch):
    _patch_ticker(monkeypatch, {"previousClose": 100.0, "currentPrice": 110.0,
                                "regularMarketChangePercent": 4.2,
                                "longName": "Test Co"})
    assert md.fetch_ticker_info("AAPL").day_change_pct == pytest.approx(4.2)


def test_ticker_info_does_not_divide_by_a_zero_previous_close(monkeypatch):
    _patch_ticker(monkeypatch, {"previousClose": 0.0, "currentPrice": 110.0,
                                "longName": "Test Co"})
    assert md.fetch_ticker_info("AAPL").day_change_pct is None


def test_ticker_info_roundtrips_to_dict(monkeypatch):
    _patch_ticker(monkeypatch, {"previousClose": 100.0, "longName": "Test Co",
                                "sector": "Technology"})
    payload = md.fetch_ticker_info("AAPL").to_dict()
    assert payload["symbol"] == "AAPL"
    assert payload["sector"] == "Technology"
    assert payload["source"] == "yfinance"
    assert payload["fetched_at"] > 0


# ==============================================================================
# Scanner
# ==============================================================================


def _history(symbols, rows=70):
    """A yfinance-shaped MultiIndex frame."""
    index = pd.date_range("2024-01-01", periods=rows, freq="B")
    frames = {}
    for i, symbol in enumerate(symbols):
        base = 100.0 + i * 10
        closes = [base + n * 0.5 for n in range(rows)]
        frames[(symbol, "Open")] = closes
        frames[(symbol, "High")] = [c + 1 for c in closes]
        frames[(symbol, "Low")] = [c - 1 for c in closes]
        frames[(symbol, "Close")] = closes
        frames[(symbol, "Volume")] = [1_000_000 + n * 1000 for n in range(rows)]
    return pd.DataFrame(frames, index=index)


def test_scanner_rejects_empty_universe():
    with pytest.raises(md.DataUnavailable):
        md.fetch_scanner_universe([])


def test_scanner_reports_partial_coverage_instead_of_filling_it(monkeypatch):
    """The old code replaced the whole record set with seeded fakes when fewer
    than five symbols resolved. Partial coverage must be reported, not topped
    up."""
    monkeypatch.setattr(md, "fetch_price_history",
                        lambda symbols, period="1y", interval="1d": _history(["AAPL", "MSFT"]))
    result = md.fetch_scanner_universe(["AAPL", "MSFT", "GONE1", "GONE2"])
    assert result.requested == 4
    assert result.resolved == 2
    assert result.coverage == pytest.approx(0.5)
    assert {r["ticker"] for r in result.records} == {"AAPL", "MSFT"}


def test_scanner_raises_when_nothing_resolves(monkeypatch):
    monkeypatch.setattr(md, "fetch_price_history",
                        lambda symbols, period="1y", interval="1d": _history(["OTHER"]))
    with pytest.raises(md.DataUnavailable):
        md.fetch_scanner_universe(["AAPL", "MSFT"])


def test_scanner_carries_the_window_it_actually_measured(monkeypatch):
    """The UI labelled a 65-day high as a '52W HIGH'."""
    monkeypatch.setattr(md, "fetch_price_history",
                        lambda symbols, period="1y", interval="1d": _history(["AAPL"]))
    result = md.fetch_scanner_universe(["AAPL"], lookback_days=65)
    assert result.window_days == 65
    assert "window_high" in result.records[0]
    assert "at_window_high" in result.records[0]


def test_scanner_computes_change_from_the_last_two_closes(monkeypatch):
    monkeypatch.setattr(md, "fetch_price_history",
                        lambda symbols, period="1y", interval="1d": _history(["AAPL"]))
    record = md.fetch_scanner_universe(["AAPL"]).records[0]
    # closes rise by 0.5 each bar from 100.0
    assert record["change"] == pytest.approx(0.5 / (record["close"] - 0.5) * 100, rel=1e-6)


def test_scanner_top_sorts_both_directions(monkeypatch):
    monkeypatch.setattr(md, "fetch_price_history",
                        lambda symbols, period="1y", interval="1d": _history(["AAPL", "MSFT", "NVDA"]))
    result = md.fetch_scanner_universe(["AAPL", "MSFT", "NVDA"])
    gainers = result.top("change", 3)
    losers = result.top("change", 3, ascending=True)
    assert gainers[0]["change"] >= gainers[-1]["change"]
    assert losers[0]["change"] <= losers[-1]["change"]


def test_scanner_result_coverage_is_zero_for_an_empty_result():
    assert md.ScannerResult().coverage == 0.0


# ==============================================================================
# News
# ==============================================================================


def test_news_rejects_empty_symbol():
    with pytest.raises(md.DataUnavailable):
        md.fetch_rss_news("")


def test_news_raises_on_transport_failure(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("connection reset")

    monkeypatch.setattr(md.requests, "get", boom)
    with pytest.raises(md.DataUnavailable):
        md.fetch_rss_news("AAPL")


class _FakeResponse:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        return None


def test_news_parses_items_and_skips_untitled(monkeypatch):
    xml = b"""<rss><channel>
        <item><title>Real headline</title><link>http://x</link><pubDate>Mon</pubDate></item>
        <item><title></title><link>http://y</link></item>
    </channel></rss>"""
    monkeypatch.setattr(md.requests, "get", lambda *a, **k: _FakeResponse(xml))
    items = md.fetch_rss_news("AAPL")
    assert len(items) == 1
    assert items[0]["headline"] == "Real headline"


def test_news_returns_empty_list_for_a_genuinely_quiet_ticker(monkeypatch):
    """No headlines is a real outcome and must not be an error."""
    monkeypatch.setattr(md.requests, "get",
                        lambda *a, **k: _FakeResponse(b"<rss><channel></channel></rss>"))
    assert md.fetch_rss_news("AAPL") == []
