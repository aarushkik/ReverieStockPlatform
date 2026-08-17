"""
HTML rendering for the Workbench.

Pure string functions - no Streamlit - so the markup can be unit-tested and so
the rules about *what gets flagged* live next to the verifier that decides it.

The memo renderer is the piece that carries the product claim into the
interface. A verified figure gets a quiet underline and a citation chip you can
hover for its provenance. An unverified one gets a visible warning treatment.
Both are rendered; neither is hidden and neither is silently corrected. The
reader is told which numbers the system could stand behind and which it could
not, which is the entire point.
"""

from __future__ import annotations

import html
import time
from typing import Dict, List, Optional, Tuple

from .engine import FAILED, OK, PENDING, RUNNING, SKIPPED, Run, Workflow
from .ledger import CITATION_WINDOW, Ledger, VerificationReport, _CITATION

__all__ = ["render_memo_html", "render_dag_html", "render_evidence_html",
           "render_verification_badge", "relative_time"]


def relative_time(timestamp: float, now: Optional[float] = None) -> str:
    """'12s ago', '4m ago', '2h ago'."""
    if not timestamp:
        return "unknown"
    delta = max(0.0, (now if now is not None else time.time()) - timestamp)
    if delta < 60:
        return f"{int(delta)}s ago"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    return f"{int(delta // 86400)}d ago"


# ==============================================================================
# MEMO
# ==============================================================================

_STATUS_STYLE = {
    "uncited": ("var(--rv-warn)", "no source for this figure"),
    "unknown_fact": ("var(--rv-neg)", "cites a fact that does not exist"),
    "mismatch": ("var(--rv-neg)", "does not match the measured value"),
}


def render_memo_html(memo: str, ledger: Ledger,
                     report: Optional[VerificationReport] = None) -> str:
    """Render the memo with citation chips and unverified figures flagged."""
    if not memo:
        return '<div class="rv-empty">No memo was produced.</div>'

    # Markup events: claim spans and citation markers. They never overlap - a
    # citation follows its claim - so a single ordered walk is enough.
    events: List[Tuple[int, int, str, object]] = []

    if report:
        for claim in report.claims:
            events.append((claim.start, claim.end, "claim", claim))

    for match in _CITATION.finditer(memo):
        events.append((match.start(), match.end(), "cite", match.group(0)))

    events.sort(key=lambda e: e[0])

    out: List[str] = []
    cursor = 0
    for start, end, kind, payload in events:
        if start < cursor:          # defensive: skip anything overlapping
            continue
        out.append(html.escape(memo[cursor:start]).replace("\n", "<br>"))
        raw = html.escape(memo[start:end])

        if kind == "claim":
            claim = payload
            if claim.ok:
                fact = ledger.get(claim.matched_fact) if claim.matched_fact else None
                tip = (f"{fact.label} = {fact.display()} · {fact.tool}/{fact.source}"
                       if fact else "verified")
                out.append(
                    f'<span class="rv-claim rv-claim--ok" title="{html.escape(tip)}">'
                    f"{raw}</span>"
                )
            else:
                color, reason = _STATUS_STYLE.get(
                    claim.status, ("var(--rv-warn)", "unverified"))
                detail = claim.detail or reason
                out.append(
                    f'<span class="rv-claim rv-claim--bad" '
                    f'style="--rv-claim-color:{color}" '
                    f'title="{html.escape(detail)}">{raw}'
                    f'<span class="rv-claim-mark">unverified</span></span>'
                )
        else:
            ids = payload.strip("[]").replace(" ", "").split(",")
            chips = []
            for fid in ids:
                fact = ledger.get(fid)
                if fact is None:
                    chips.append(
                        f'<span class="rv-cite rv-cite--missing" '
                        f'title="no such fact">{html.escape(fid)}</span>'
                    )
                else:
                    tip = (f"{fact.label} = {fact.display()}\n"
                           f"{fact.tool} via {fact.source}\n"
                           f"fetched {relative_time(fact.fetched_at)}")
                    chips.append(
                        f'<span class="rv-cite" title="{html.escape(tip)}">'
                        f"{html.escape(fid)}</span>"
                    )
            out.append("".join(chips))
        cursor = end

    out.append(html.escape(memo[cursor:]).replace("\n", "<br>"))
    return f'<div class="rv-memo">{"".join(out)}</div>'


def render_verification_badge(report: Optional[VerificationReport]) -> str:
    """A one-line summary of how much of the memo checked out."""
    if report is None:
        return ""
    if report.total == 0:
        return ('<span class="pill-neut">no numeric claims</span>')

    rate = report.pass_rate
    if rate == 1.0:
        cls, label = "pill-pos", "every figure verified"
    elif rate >= 0.75:
        cls, label = "pill-neut", f"{report.verified}/{report.total} figures verified"
    else:
        cls, label = "pill-neg", f"only {report.verified}/{report.total} verified"
    return f'<span class="{cls}">{label}</span>'


# ==============================================================================
# DAG
# ==============================================================================

_STEP_TONE = {
    OK: ("var(--rv-pos)", "done"),
    FAILED: ("var(--rv-neg)", "failed"),
    RUNNING: ("var(--rv-accent-fill)", "running"),
    SKIPPED: ("var(--rv-text-faint)", "skipped"),
    PENDING: ("var(--rv-border-hi)", "waiting"),
}


def render_dag_html(workflow: Workflow, run: Optional[Run] = None) -> str:
    """The workflow as dependency levels, with live per-step status."""
    from .engine import _order

    levels = _order(list(workflow.steps))
    columns: List[str] = []

    for depth, level in enumerate(levels):
        cards = []
        for step in level:
            status = (run.step_status.get(step.id, PENDING) if run else PENDING)
            tone, label = _STEP_TONE.get(status, _STEP_TONE[PENDING])
            result = run.results.get(step.id) if run else None

            if result is not None and result.ok:
                detail = f"{result.duration_ms:.0f} ms · {result.source}"
            elif result is not None:
                detail = html.escape((result.error or "failed")[:70])
            elif status == SKIPPED:
                detail = "dependency did not complete"
            else:
                detail = html.escape(step.tool)

            optional = "" if step.required else (
                '<span class="rv-step-optional">optional</span>')

            cards.append(
                f'<div class="rv-step" style="--rv-step-tone:{tone}">'
                f'<div class="rv-step-head">'
                f'<span class="rv-step-dot"></span>'
                f'<span class="rv-step-name">{html.escape(step.display())}</span>'
                f"{optional}</div>"
                f'<div class="rv-step-meta">{detail}</div>'
                f'<div class="rv-step-status">{label}</div>'
                f"</div>"
            )

        columns.append(
            f'<div class="rv-dag-level">'
            f'<div class="rv-dag-level-label">step {depth + 1}</div>'
            f'{"".join(cards)}</div>'
        )

    return f'<div class="rv-dag">{"".join(columns)}</div>'


# ==============================================================================
# EVIDENCE
# ==============================================================================


def render_evidence_html(ledger: Ledger, limit: int = 120) -> str:
    """Every fact the run measured, with where it came from."""
    facts = ledger.facts
    if not facts:
        return ('<div class="rv-empty"><span class="rv-empty-icon">◇</span>'
                "<span>No facts were measured.</span></div>")

    rows = []
    for fact in facts[:limit]:
        rows.append(
            "<tr>"
            f'<td class="rv-sym">{html.escape(fact.fact_id)}</td>'
            f"<td>{html.escape(fact.label)}</td>"
            f'<td class="rv-right">{html.escape(fact.display())}</td>'
            f"<td>{html.escape(fact.tool)}</td>"
            f"<td>{html.escape(fact.source)}</td>"
            f'<td class="rv-right">{relative_time(fact.fetched_at)}</td>'
            "</tr>"
        )

    more = ""
    if len(facts) > limit:
        more = (f'<div class="rv-caption" style="padding:var(--rv-space-2)">'
                f"{len(facts) - limit} more not shown</div>")

    return (
        '<div class="rv-card rv-card--flush" style="overflow-x:auto">'
        "<table><thead><tr>"
        "<th>ID</th><th>Measurement</th><th class=\"rv-right\">Value</th>"
        "<th>Tool</th><th>Source</th><th class=\"rv-right\">Fetched</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>" + more + "</div>"
    )
