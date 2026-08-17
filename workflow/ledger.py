"""
The fact ledger and citation verifier.

This is where the product claim stops being a prompt instruction and becomes a
checked property.

Asking a model to cite its sources is easy and worth very little: the model
will happily attach a plausible-looking citation to a number it made up, and
nothing catches it. The ledger closes that loop.

    1.  Every scalar a tool produced is registered as a :class:`Fact` with an
        id (``f7``), its value, its unit, and the tool call it came from.
    2.  The synthesis prompt is built from the fact table, and the model is told
        to cite ids inline.
    3.  :func:`verify` then re-reads the model's prose, extracts every numeric
        claim, and checks each one against the fact it cites - that a citation
        exists at all, that the id resolves, and that **the number in the text
        actually equals the number in the ledger**.

Step 3 is the part that matters. A claim with no citation, a citation pointing
at a fact that does not exist, or a citation whose value disagrees with the
prose all come back flagged, and the UI renders them as unverified rather than
as analysis.

The verifier is deliberately conservative about what counts as a claim: years,
list numbering, and numbers inside citation markers are not claims, because
flagging them would train the reader to ignore the warnings.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .tools import ToolResult

__all__ = [
    "Fact",
    "Ledger",
    "Claim",
    "VerificationReport",
    "verify",
]

# Relative tolerance when comparing a number in prose against the ledger.
# Models legitimately round: "$182.40" for 182.3956 is a faithful restatement,
# "$192.40" is not.
MATCH_RTOL = 0.005
MATCH_ATOL = 1e-9

# A citation must appear within this many characters after the number.
CITATION_WINDOW = 60


# ==============================================================================
# FACTS
# ==============================================================================


@dataclass(frozen=True)
class Fact:
    """One measured value, traceable to the call that produced it."""

    fact_id: str
    label: str
    value: float
    unit: str
    call_id: str
    tool: str
    source: str
    fetched_at: float

    def render(self) -> str:
        """One line of the fact table shown to the model."""
        return f"[{self.fact_id}] {self.label} = {self.display()}  (via {self.tool}/{self.source})"

    def display(self) -> str:
        """Human-readable value, matching how the UI renders it."""
        magnitude = abs(self.value)
        if self.unit == "pct":
            return f"{self.value:.2f}%"
        if self.unit == "usd":
            # Large caps as compact magnitudes: a fourteen-digit market cap is
            # unreadable in a fact table and invites the model to restate it as
            # "$4.46T" anyway, which the verifier accepts.
            for cutoff, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
                if magnitude >= cutoff:
                    return f"${self.value / cutoff:,.2f}{suffix}"
            return f"${self.value:,.2f}"
        if magnitude >= 1000:
            return f"{self.value:,.2f}"
        return f"{self.value:.4g}"


# Heuristics for labelling units from the key name. Units matter because the
# UI renders them and because a unit mismatch is a real error class.
#
# RSI is deliberately absent: it is a 0-100 index, not a percentage, and
# printing "61.80%" in the fact table teaches the model to write it wrongly.
_PCT_HINTS = ("pct", "percent", "_change", "yield", "volatility")
_USD_HINTS = ("price", "close", "open", "high", "low", "bid", "ask", "cap",
              "value", "cash", "eps", "cost", "total")
# Dimensionless quantities that would otherwise be caught by a broader hint.
_UNITLESS = ("rsi", "beta", "ratio", "score", "count", "volume", "shares",
             "observations", "pe_ratio")


def _infer_unit(label: str) -> str:
    lowered = label.lower()
    if any(h in lowered for h in _UNITLESS):
        return ""
    if any(h in lowered for h in _PCT_HINTS):
        return "pct"
    if any(h in lowered for h in _USD_HINTS):
        return "usd"
    return ""


def _is_real_number(value: Any) -> bool:
    if isinstance(value, bool):          # bools are ints in Python; not facts
        return False
    if not isinstance(value, (int, float)):
        return False
    return not (math.isnan(value) or math.isinf(value))


class Ledger:
    """Collects facts from tool results and renders them for the model."""

    def __init__(self) -> None:
        self._facts: List[Fact] = []
        self._by_id: Dict[str, Fact] = {}
        self._counter = 0

    # ---- building -------------------------------------------------------
    def add_from_result(self, result: ToolResult, prefix: str = "") -> List[Fact]:
        """Register every scalar in a successful tool result.

        A failed result contributes nothing - which is the mechanism by which a
        broken fetch makes the corresponding claim impossible to state rather
        than merely unlikely.
        """
        if not result.ok or result.value is None:
            return []

        added: List[Fact] = []
        base = prefix or result.tool
        for label, value in self._walk(result.value, base):
            if not _is_real_number(value):
                continue
            self._counter += 1
            fact = Fact(
                fact_id=f"f{self._counter}",
                label=label,
                value=float(value),
                unit=_infer_unit(label),
                call_id=result.call_id,
                tool=result.tool,
                source=result.source,
                fetched_at=result.fetched_at,
            )
            self._facts.append(fact)
            self._by_id[fact.fact_id] = fact
            added.append(fact)
        return added

    def _walk(self, value: Any, prefix: str) -> Iterable[Tuple[str, Any]]:
        """Flatten nested dicts/lists into dotted labels."""
        if isinstance(value, dict):
            for key, sub in value.items():
                yield from self._walk(sub, f"{prefix}.{key}")
        elif isinstance(value, (list, tuple)):
            # Only index into short lists; a 500-row price series would swamp
            # the fact table and none of it would ever be cited.
            if len(value) <= 12:
                for i, sub in enumerate(value):
                    yield from self._walk(sub, f"{prefix}[{i}]")
        else:
            yield prefix, value

    # ---- access ---------------------------------------------------------
    @property
    def facts(self) -> List[Fact]:
        return list(self._facts)

    def get(self, fact_id: str) -> Optional[Fact]:
        return self._by_id.get(fact_id)

    def __len__(self) -> int:
        return len(self._facts)

    def render_table(self, limit: int = 200) -> str:
        """The fact table injected into the synthesis prompt."""
        if not self._facts:
            return "(no facts were successfully measured)"
        return "\n".join(f.render() for f in self._facts[:limit])

    def to_json(self) -> List[Dict[str, Any]]:
        return [
            {
                "fact_id": f.fact_id, "label": f.label, "value": f.value,
                "unit": f.unit, "call_id": f.call_id, "tool": f.tool,
                "source": f.source, "fetched_at": f.fetched_at,
            }
            for f in self._facts
        ]


# ==============================================================================
# VERIFICATION
# ==============================================================================


@dataclass
class Claim:
    """A numeric assertion found in the model's prose."""

    text: str               # the number as written, e.g. "$182.40"
    value: float            # parsed
    start: int              # character offset in the memo
    end: int
    cited: List[str] = field(default_factory=list)   # fact ids found nearby
    status: str = "unverified"   # "verified" | "uncited" | "unknown_fact" | "mismatch"
    matched_fact: Optional[str] = None
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "verified"


@dataclass
class VerificationReport:
    claims: List[Claim] = field(default_factory=list)
    unknown_citations: List[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.claims)

    @property
    def verified(self) -> int:
        return sum(1 for c in self.claims if c.ok)

    @property
    def flagged(self) -> List[Claim]:
        return [c for c in self.claims if not c.ok]

    @property
    def pass_rate(self) -> float:
        return (self.verified / self.total) if self.total else 1.0

    def to_json(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "verified": self.verified,
            "pass_rate": round(self.pass_rate, 4),
            "unknown_citations": self.unknown_citations,
            "claims": [
                {
                    "text": c.text, "value": c.value, "status": c.status,
                    "cited": c.cited, "matched_fact": c.matched_fact,
                    "detail": c.detail, "start": c.start, "end": c.end,
                }
                for c in self.claims
            ],
        }


# A number, optionally with a currency prefix, thousands separators, decimals,
# a percent sign, or a magnitude suffix.
_NUMBER = re.compile(
    r"(?<![\w.])"                     # not mid-identifier
    r"(?P<full>"
    r"(?P<cur>[$€£])?"
    r"(?P<sign>[-+])?"
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?P<suffix>\s?%|[KMBT]\b)?"
    r")"
)
_CITATION = re.compile(r"\[(f\d+)((?:\s*,\s*f\d+)*)\]")
_MAGNITUDE = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}


def _parse_number(match: re.Match) -> Optional[float]:
    raw = match.group("num").replace(",", "")
    try:
        value = float(raw)
    except ValueError:
        return None
    if match.group("sign") == "-":
        value = -value
    suffix = (match.group("suffix") or "").strip()
    if suffix in _MAGNITUDE:
        value *= _MAGNITUDE[suffix]
    return value


def _is_ignorable(match: re.Match, text: str) -> bool:
    """Numbers that are not claims about the world."""
    full = match.group("full")
    value = _parse_number(match)
    if value is None:
        return True

    # Inside a citation marker, e.g. the 7 in "[f7]".
    if match.start() > 0 and text[match.start() - 1] == "f":
        preceding = text[max(0, match.start() - 2):match.start()]
        if preceding.endswith("[f") or preceding.endswith(" f"):
            return True

    # Bare 4-digit years, with no currency or percent attached.
    if (not match.group("cur") and not match.group("suffix")
            and full.isdigit() and 1900 <= value <= 2100):
        return True

    # Markdown list numbering / headings at line start: "1. ", "2) "
    line_start = text.rfind("\n", 0, match.start()) + 1
    if text[line_start:match.start()].strip() in ("", "#", "##", "###", "-", "*"):
        after = text[match.end():match.end() + 2]
        if after.startswith(".") or after.startswith(")"):
            return True

    return False


def _values_match(claimed: float, actual: float) -> bool:
    if math.isclose(claimed, actual, rel_tol=MATCH_RTOL, abs_tol=MATCH_ATOL):
        return True
    # A percentage may be written either as 3.42 or 0.0342 depending on how the
    # model chose to phrase it; accept the scaled form rather than crying wolf.
    if actual != 0 and math.isclose(claimed, actual * 100.0,
                                    rel_tol=MATCH_RTOL, abs_tol=MATCH_ATOL):
        return True
    if claimed != 0 and math.isclose(claimed * 100.0, actual,
                                     rel_tol=MATCH_RTOL, abs_tol=MATCH_ATOL):
        return True
    return False


def verify(text: str, ledger: Ledger) -> VerificationReport:
    """Check every numeric claim in *text* against *ledger*.

    Returns a report; it never raises and never edits the text. Rendering is the
    caller's job.
    """
    report = VerificationReport()
    if not text:
        return report

    # Citations present anywhere, so unresolvable ids are reported even when
    # they are not attached to a number.
    for match in _CITATION.finditer(text):
        for fid in re.findall(r"f\d+", match.group(0)):
            if ledger.get(fid) is None and fid not in report.unknown_citations:
                report.unknown_citations.append(fid)

    for match in _NUMBER.finditer(text):
        if _is_ignorable(match, text):
            continue
        value = _parse_number(match)
        if value is None:
            continue

        claim = Claim(
            text=match.group("full"), value=value,
            start=match.start(), end=match.end(),
        )

        window = text[match.end():match.end() + CITATION_WINDOW]
        # Stop at a sentence boundary so a citation belonging to the *next*
        # sentence cannot launder this one.
        boundary = window.find(". ")
        if boundary != -1:
            window = window[:boundary]

        cited: List[str] = []
        for cite in _CITATION.finditer(window):
            cited.extend(re.findall(r"f\d+", cite.group(0)))
        claim.cited = cited

        if not cited:
            claim.status = "uncited"
            claim.detail = "no citation follows this figure"
            report.claims.append(claim)
            continue

        resolved = [(fid, ledger.get(fid)) for fid in cited]
        known = [(fid, fact) for fid, fact in resolved if fact is not None]
        if not known:
            claim.status = "unknown_fact"
            claim.detail = f"cites {', '.join(cited)}, which is not in the ledger"
            report.claims.append(claim)
            continue

        match_found = next(
            (fid for fid, fact in known if _values_match(value, fact.value)), None
        )
        if match_found:
            claim.status = "verified"
            claim.matched_fact = match_found
        else:
            claim.status = "mismatch"
            expected = ", ".join(f"{fid}={fact.value:g}" for fid, fact in known)
            claim.detail = f"text says {value:g}; ledger has {expected}"
        report.claims.append(claim)

    return report
