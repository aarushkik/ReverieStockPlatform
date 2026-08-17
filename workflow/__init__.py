"""Verifiable AI research workflows over real market data.

The premise: an AI answer about money is worthless unless you can check it. A
workflow here is a DAG of typed tool calls over measured data, followed by a
synthesis step whose every numeric claim is verified against the facts those
tools actually produced.

    tools.py         the registry - what a workflow can do, and what happened
    market_tools.py  the concrete tools (importing this registers them)
    ledger.py        the fact table and the citation verifier
    engine.py        the DAG executor and the run record
    templates.py     prebuilt workflows

Two properties worth stating up front, because they are unusual:

*   The workflow chooses the tools, not the model. Runs are therefore
    reproducible and can be replayed and diffed.
*   A failed required step halts the run and no memo is written. The engine
    would rather say nothing than let a model paper over a missing fetch.
"""

from . import ledger, tools           # noqa: F401  (order matters)
from . import market_tools            # noqa: F401  registers the tools
from . import engine, templates       # noqa: F401
from .engine import Run, Step, Synthesis, Workflow, execute
from .ledger import Fact, Ledger, verify
from .templates import TEMPLATES, get_template, list_templates
from .tools import ToolResult, list_tools

__all__ = [
    "Run", "Step", "Synthesis", "Workflow", "execute",
    "Fact", "Ledger", "verify",
    "TEMPLATES", "get_template", "list_templates",
    "ToolResult", "list_tools",
    "tools", "ledger", "engine", "templates", "market_tools",
]
