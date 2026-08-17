"""Verifiable AI research workflows over real market data.

The premise: an AI answer about money is worthless unless you can check it. A
workflow here is a DAG of typed tool calls over measured data, followed by a
synthesis step whose every numeric claim is verified against the facts those
tools actually produced.

    tools.py   the registry - what a workflow can do, and what happened when it did
    ledger.py  the fact table and the citation verifier
"""

from . import ledger, tools  # noqa: F401

__all__ = ["tools", "ledger"]
