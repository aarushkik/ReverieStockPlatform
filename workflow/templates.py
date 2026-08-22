"""
Prebuilt workflows.

Each is a declarative DAG plus a synthesis brief. They are ordinary data, so
the UI can render them, a user can copy and edit one, and a test can run one
against fake tools.

Note what the synthesis prompts do *not* ask for. None of them requests a
recommendation, a price target or a rating. The engine can guarantee that every
number in the output was measured; it cannot guarantee that a judgement built
on those numbers is sound, so the workflows stay descriptive and leave the
inference to the reader.
"""

from __future__ import annotations

from typing import Dict, List

from .engine import Step, Synthesis, Workflow

__all__ = ["TEMPLATES", "get_template", "list_templates"]


DUE_DILIGENCE = Workflow(
    key="due_diligence",
    name="Due diligence",
    description=(
        "Full first-pass review of a single symbol: price action, technicals, "
        "patterns, fundamentals, news and sentiment."
    ),
    inputs=("symbol",),
    steps=(
        Step(
            id="prices",
            tool="prices",
            args={"symbol": "$input.symbol", "period": "1y"},
            label="Fetch 1y price history",
        ),
        # These three reuse the history the first step already downloaded,
        # rather than each triggering its own fetch.
        Step(
            id="indicators",
            tool="indicators",
            args={"symbol": "$input.symbol", "history": "$artifact:prices"},
            depends_on=("prices",),
            label="Compute indicators",
        ),
        Step(
            id="patterns",
            tool="patterns",
            args={"symbol": "$input.symbol", "history": "$artifact:prices"},
            depends_on=("prices",),
            label="Detect patterns",
            required=False,
        ),
        Step(
            id="fundamentals",
            tool="fundamentals",
            args={"symbol": "$input.symbol"},
            label="Fetch fundamentals",
            required=False,
        ),
        Step(
            id="news",
            tool="news",
            args={"symbol": "$input.symbol", "limit": 10},
            label="Fetch headlines",
            required=False,
        ),
        Step(
            id="sentiment",
            tool="sentiment",
            args={"headlines": "$value:news.headlines", "symbol": "$input.symbol"},
            depends_on=("news",),
            label="Score sentiment",
            required=False,
        ),
    ),
    synthesis=Synthesis(
        prompt=(
            "Write a short due-diligence note on the symbol below. Cover, in "
            "this order: where the price sits relative to its own recent range "
            "and moving averages; what the momentum indicators say; any "
            "patterns detected; the valuation picture; and what the recent "
            "headlines are about. Finish with a short list of what the data "
            "does NOT tell us. Do not give a recommendation."
        ),
        label="Write due-diligence note",
    ),
)


WHY_DID_IT_MOVE = Workflow(
    key="why_move",
    name="Why did this move?",
    description=(
        "Explain a symbol's recent price action against the headlines and "
        "technical picture, with competing explanations ranked."
    ),
    inputs=("symbol",),
    steps=(
        Step(id="prices", tool="prices",
             args={"symbol": "$input.symbol", "period": "3mo"},
             label="Fetch 3mo price history"),
        Step(id="indicators", tool="indicators",
             args={"symbol": "$input.symbol", "history": "$artifact:prices"},
             depends_on=("prices",), label="Compute indicators"),
        Step(id="news", tool="news",
             args={"symbol": "$input.symbol", "limit": 15},
             label="Fetch headlines", required=False),
        Step(id="sentiment", tool="sentiment",
             args={"headlines": "$value:news.headlines", "symbol": "$input.symbol"},
             depends_on=("news",), label="Score sentiment", required=False),
    ),
    synthesis=Synthesis(
        prompt=(
            "Explain the symbol's recent price action. Offer the two or three "
            "most plausible explanations, ranked, and say explicitly how "
            "confident the available evidence lets you be in each. Where the "
            "headlines do not account for the move, say that outright rather "
            "than inventing a cause. Correlation between a headline and a price "
            "move is not evidence of causation - be careful to say which you "
            "are describing."
        ),
        label="Explain the move",
    ),
)


WHAT_WOULD_MAKE_ME_WRONG = Workflow(
    key="disconfirm",
    name="What would make me wrong?",
    description=(
        "Takes a thesis and gathers the evidence against it, rather than for it."
    ),
    inputs=("symbol", "thesis"),
    steps=(
        Step(id="prices", tool="prices",
             args={"symbol": "$input.symbol", "period": "1y"},
             label="Fetch 1y price history"),
        Step(id="indicators", tool="indicators",
             args={"symbol": "$input.symbol", "history": "$artifact:prices"},
             depends_on=("prices",), label="Compute indicators"),
        Step(id="fundamentals", tool="fundamentals",
             args={"symbol": "$input.symbol"},
             label="Fetch fundamentals", required=False),
        Step(id="news", tool="news",
             args={"symbol": "$input.symbol", "limit": 15},
             label="Fetch headlines", required=False),
        Step(id="sentiment", tool="sentiment",
             args={"headlines": "$value:news.headlines", "symbol": "$input.symbol"},
             depends_on=("news",), label="Score sentiment", required=False),
    ),
    synthesis=Synthesis(
        prompt=(
            "The user holds the stated thesis. Your job is to argue against it "
            "using only the measured facts. List the strongest disconfirming "
            "evidence, then state which specific, observable events would show "
            "the thesis to be wrong. If the available data does not contradict "
            "the thesis, say so plainly - do not manufacture a counter-argument. "
            "End by naming what evidence you would want but do not have."
        ),
        label="Argue the other side",
    ),
)


PORTFOLIO_BRIEF = Workflow(
    key="portfolio_brief",
    name="Portfolio brief",
    description="What moved in the positions you actually hold, and why.",
    inputs=("positions", "symbols"),
    steps=(
        Step(id="portfolio", tool="portfolio",
             args={"positions": "$input.positions"},
             label="Read positions"),
        Step(id="scan", tool="scanner",
             args={"symbols": "$input.symbols", "lookback_days": 30},
             depends_on=("portfolio",),
             label="Scan held symbols"),
    ),
    synthesis=Synthesis(
        prompt=(
            "Summarise what happened across the user's holdings. Lead with the "
            "largest movers. Note the scan's coverage - if some holdings could "
            "not be priced, say which and do not average them away. Describe "
            "only what the data shows."
        ),
        label="Write portfolio brief",
    ),
)


QUANT_OUTLOOK = Workflow(
    key="quant_outlook",
    name="Quantitative outlook",
    description=(
        "Train a direction classifier on the symbol's own history, report its "
        "backtested accuracy, and read it against the current technical picture."
    ),
    inputs=("symbol",),
    steps=(
        Step(id="prices", tool="prices",
             args={"symbol": "$input.symbol", "period": "2y"},
             label="Fetch 2y price history"),
        Step(id="indicators", tool="indicators",
             args={"symbol": "$input.symbol", "history": "$artifact:prices"},
             depends_on=("prices",), label="Compute indicators"),
        Step(id="forecast", tool="forecast",
             args={"symbol": "$input.symbol", "history": "$artifact:prices"},
             depends_on=("prices",), label="Train direction model"),
    ),
    synthesis=Synthesis(
        prompt=(
            "Report what the trained model found. Lead with its backtested "
            "accuracy and the sample sizes it was trained and tested on, "
            "because those determine how much weight the direction call "
            "deserves. State plainly if the accuracy is close to 50% — that "
            "means the model has found no reliable edge, and saying so is the "
            "correct outcome, not a failure to report. Then describe how the "
            "signal sits against the current indicators. Do not translate any "
            "of this into a recommendation."
        ),
        label="Report the model's findings",
    ),
)


TEMPLATES: Dict[str, Workflow] = {
    w.key: w for w in (
        DUE_DILIGENCE,
        WHY_DID_IT_MOVE,
        WHAT_WOULD_MAKE_ME_WRONG,
        PORTFOLIO_BRIEF,
        QUANT_OUTLOOK,
    )
}


def get_template(key: str) -> Workflow:
    if key not in TEMPLATES:
        raise KeyError(f"unknown workflow {key!r}; known: {sorted(TEMPLATES)}")
    return TEMPLATES[key]


def list_templates() -> List[Workflow]:
    return list(TEMPLATES.values())
