"""Tests for workflow/ledger.py.

This is the file that decides whether "every claim carries a receipt" is a real
property or a prompt instruction. The cases that matter most are the adversarial
ones: a model that cites a fact but states a different number, and a model that
cites an id that does not exist.
"""

import math
import time

import pytest

from workflow.ledger import Fact, Ledger, verify
from workflow.tools import ToolResult


def _result(value, ok=True, call_id="t1", tool="fundamentals",
            source="yfinance", error=None):
    return ToolResult(
        call_id=call_id, tool=tool, args={}, ok=ok, value=value,
        error=error, source=source, fetched_at=time.time(),
    )


@pytest.fixture
def ledger():
    led = Ledger()
    led.add_from_result(_result({
        "previous_close": 182.3956,
        "pe_ratio": 54.2,
        "market_cap": 4.46e12,
        "day_change_pct": 3.42,
    }))
    led.add_from_result(_result({"rsi_14": 61.8}, call_id="t2",
                                tool="indicators", source="computed"))
    return led


# ==============================================================================
# Fact collection
# ==============================================================================


def test_scalars_become_facts(ledger):
    assert len(ledger) == 5
    assert ledger.get("f1").label == "fundamentals.previous_close"
    assert ledger.get("f1").value == pytest.approx(182.3956)


def test_facts_carry_their_origin(ledger):
    fact = ledger.get("f5")
    assert fact.tool == "indicators"
    assert fact.call_id == "t2"
    assert fact.source == "computed"
    assert fact.fetched_at > 0


def test_a_failed_tool_contributes_no_facts():
    """The mechanism by which a broken fetch makes a claim unstatable."""
    led = Ledger()
    led.add_from_result(_result(None, ok=False, error="timeout"))
    assert len(led) == 0
    assert "no facts" in led.render_table()


def test_booleans_are_not_facts():
    # bool is a subclass of int; "at_window_high = True" is not a measurement
    # anyone should cite as a number.
    led = Ledger()
    led.add_from_result(_result({"at_window_high": True, "close": 10.0}))
    assert len(led) == 1
    assert led.get("f1").label.endswith("close")


def test_nan_and_infinity_are_not_facts():
    led = Ledger()
    led.add_from_result(_result({"a": float("nan"), "b": float("inf"), "c": 1.0}))
    assert len(led) == 1


def test_strings_are_not_facts():
    led = Ledger()
    led.add_from_result(_result({"name": "Apple Inc.", "close": 10.0}))
    assert len(led) == 1


def test_nested_dicts_are_flattened():
    led = Ledger()
    led.add_from_result(_result({"quote": {"bid": 1.5, "ask": 1.6}}))
    assert {f.label for f in led.facts} == {
        "fundamentals.quote.bid", "fundamentals.quote.ask"}


def test_short_lists_are_indexed_but_long_ones_are_not():
    led = Ledger()
    led.add_from_result(_result({"recent": [1.0, 2.0, 3.0]}))
    assert len(led) == 3

    led2 = Ledger()
    led2.add_from_result(_result({"series": list(range(500))}))
    # A 500-row price series would swamp the table and never be cited.
    assert len(led2) == 0


# ==============================================================================
# Units and rendering
# ==============================================================================


@pytest.mark.parametrize("label, expected", [
    ("x.day_change_pct", "pct"),
    ("x.volatility_pct", "pct"),
    ("x.previous_close", "usd"),
    ("x.market_cap", "usd"),
    ("x.rsi_14", ""),        # an index, not a percentage
    ("x.beta", ""),
    ("x.pe_ratio", ""),
    ("x.volume", ""),
])
def test_unit_inference(label, expected):
    from workflow.ledger import _infer_unit
    assert _infer_unit(label) == expected


def test_large_currency_renders_compactly():
    fact = Fact("f1", "x.market_cap", 4.46e12, "usd", "t1", "f", "s", 0.0)
    assert fact.display() == "$4.46T"


def test_ordinary_currency_renders_in_full():
    fact = Fact("f1", "x.close", 182.3956, "usd", "t1", "f", "s", 0.0)
    assert fact.display() == "$182.40"


# ==============================================================================
# Verification — the adversarial cases
# ==============================================================================


def test_a_faithful_cited_claim_verifies(ledger):
    report = verify("NVDA closed at $182.40 [f1].", ledger)
    assert report.total == 1
    assert report.verified == 1
    assert report.claims[0].matched_fact == "f1"


def test_rounding_is_accepted(ledger):
    # $182.40 for 182.3956 is a faithful restatement.
    assert verify("Closed at $182.40 [f1].", ledger).verified == 1


def test_a_materially_different_number_is_not_accepted(ledger):
    assert verify("Closed at $192.40 [f1].", ledger).flagged[0].status == "mismatch"


def test_an_uncited_number_is_flagged(ledger):
    report = verify("NVDA closed at $182.40 and momentum is building.", ledger)
    assert report.flagged[0].status == "uncited"
    assert report.pass_rate == 0.0


def test_a_citation_that_does_not_resolve_is_flagged(ledger):
    report = verify("Sentiment was 0.71 [f99].", ledger)
    assert report.flagged[0].status == "unknown_fact"
    assert "f99" in report.unknown_citations


def test_citing_the_wrong_fact_is_caught(ledger):
    """The whole point: a plausible citation attached to a wrong number."""
    report = verify("The P/E is 182.40 [f4].", ledger)   # f4 is the 3.42% change
    claim = report.flagged[0]
    assert claim.status == "mismatch"
    assert "ledger has" in claim.detail


def test_multiple_citations_verify_if_any_matches(ledger):
    assert verify("Closed at $182.40 [f1, f2].", ledger).verified == 1


def test_a_citation_in_the_next_sentence_cannot_launder_a_claim(ledger):
    report = verify("Closed at $182.40. The RSI is 61.8 [f5].", ledger)
    statuses = {c.text: c.status for c in report.claims}
    assert statuses["$182.40"] == "uncited"
    assert statuses["61.8"] == "verified"


# ==============================================================================
# Verification — things that are not claims
# ==============================================================================


def test_years_are_not_claims(ledger):
    assert verify("Since 2024 the trend has held.", ledger).total == 0


def test_a_year_with_a_currency_sign_is_a_claim(ledger):
    assert verify("It cost $2024 last quarter.", ledger).total == 1


def test_list_numbering_is_not_a_claim(ledger):
    report = verify("1. First point\n2. Second point\n", ledger)
    assert report.total == 0


def test_citation_ids_are_not_counted_as_claims(ledger):
    report = verify("Closed at $182.40 [f1].", ledger)
    assert report.total == 1     # not 2 - the "1" in [f1] is not a number claim


def test_empty_text_verifies_vacuously(ledger):
    report = verify("", ledger)
    assert report.total == 0
    assert report.pass_rate == 1.0


def test_prose_with_no_numbers_verifies_vacuously(ledger):
    report = verify("The setup looks constructive but risks remain.", ledger)
    assert report.total == 0
    assert report.pass_rate == 1.0


# ==============================================================================
# Number parsing
# ==============================================================================


@pytest.mark.parametrize("text, matches", [
    ("Cap is $4.46T [f3].", True),
    ("Cap is 4,460,000,000,000 [f3].", True),
])
def test_magnitude_and_separator_forms_both_match(ledger, text, matches):
    assert (verify(text, ledger).verified == 1) is matches


def test_percent_scaling_is_tolerated(ledger):
    # A model may write a 3.42% change as either 3.42 or 0.0342.
    assert verify("Up 3.42% [f4].", ledger).verified == 1
    assert verify("Up 0.0342 [f4].", ledger).verified == 1


def test_negative_numbers_parse(ledger):
    led = Ledger()
    led.add_from_result(_result({"change": -4.2}))
    assert verify("Down -4.2 [f1].", led).verified == 1


# ==============================================================================
# Reporting
# ==============================================================================


def test_report_serializes(ledger):
    payload = verify("Closed at $182.40 [f1] and $999.00 [f1].", ledger).to_json()
    assert payload["total"] == 2
    assert payload["verified"] == 1
    assert payload["pass_rate"] == 0.5
    assert len(payload["claims"]) == 2


def test_ledger_serializes(ledger):
    rows = ledger.to_json()
    assert len(rows) == 5
    assert {"fact_id", "label", "value", "unit", "call_id",
            "tool", "source", "fetched_at"} <= set(rows[0])


def test_claim_offsets_point_at_the_text(ledger):
    text = "NVDA closed at $182.40 [f1]."
    claim = verify(text, ledger).claims[0]
    assert text[claim.start:claim.end] == "$182.40"


# ==============================================================================
# False positives observed against a live model
# ==============================================================================
# Every case here was produced by a real model writing a real memo. Each one was
# flagged as unverified when it should not have been. False positives are how a
# warning system gets trained out of a reader's attention, so they are pinned.


@pytest.fixture
def indicator_ledger():
    led = Ledger()
    led.add_from_result(_result(
        {"sma_20": 314.2, "sma_60": 309.261, "rsi_14": 47.3986, "close": 309.35},
        tool="indicators", source="computed"))
    return led


@pytest.mark.parametrize("text", [
    "The close is below its SMA-20 of $314.20 [f1].",
    "It sits near its SMA 60 of $309.26 [f2].",
    "Momentum indicators show an RSI-14 of 47.4 [f3].",
    "RSI 14 sits at 47.4 [f3].",
    "The EMA-9 and MACD-12 both turned.",
])
def test_an_indicators_own_parameter_is_not_a_claim(indicator_ledger, text):
    """A model wrote "its SMA-20 of $314.20 [f27]" and the verifier flagged the
    20, matching it against the citation belonging to the price beside it."""
    report = verify(text, indicator_ledger)
    assert report.flagged == []


def test_the_indicator_rule_does_not_swallow_real_claims(indicator_ledger):
    # The price after "SMA-20 of" is still a claim and still checked.
    report = verify("The close is below its SMA-20 of $999.00 [f1].", indicator_ledger)
    assert len(report.flagged) == 1
    assert report.flagged[0].text == "$999.00"


def test_window_and_indicator_forms_both_pass(indicator_ledger):
    report = verify("The 20-day SMA is $314.20 [f1] and the RSI-14 is 47.4 [f3].",
                    indicator_ledger)
    assert report.total == 2
    assert report.verified == 2
