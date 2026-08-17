"""
The workflow engine: a DAG of tool calls, then a verified synthesis step.

**The model does not choose the tools.** The workflow declares them, and the
engine runs them in dependency order. The LLM's job is to reason over output it
did not select. This is a deliberate trade: it gives up open-ended agency and
buys reproducibility - the same workflow on the same day makes the same calls,
so a run can be replayed, diffed, and audited. Letting a model decide its own
tool sequence is the flakiest part of most agent systems and the hardest part
to explain when a number turns out wrong.

**A failed required step halts the run and no memo is produced.** This is the
central behaviour, not an error path. If the price fetch fails, the correct
output is "we could not establish the price", and the only way to guarantee a
model does not paper over that is to never give it the chance.

Argument references let one step consume another's output without tools
knowing about each other:

    "$input.symbol"        a value from the run's inputs
    "$artifact:fetch"      the heavy in-process object from step `fetch`
    "$value:fetch.last_close"   a field of step `fetch`'s JSON value
"""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from .ledger import Ledger, VerificationReport, verify
from .tools import ToolResult, call, get_spec

__all__ = [
    "Step",
    "Synthesis",
    "Workflow",
    "Run",
    "execute",
    "PENDING", "RUNNING", "OK", "FAILED", "SKIPPED",
]

PENDING = "pending"
RUNNING = "running"
OK = "ok"
FAILED = "failed"
SKIPPED = "skipped"


# ==============================================================================
# DEFINITION
# ==============================================================================


@dataclass(frozen=True)
class Step:
    """One tool invocation in a workflow."""

    id: str
    tool: str
    args: Dict[str, Any] = field(default_factory=dict)
    depends_on: Sequence[str] = field(default_factory=tuple)
    label: str = ""
    # A non-required step may fail without stopping the run; its facts simply
    # never exist, so nothing can cite them.
    required: bool = True

    def display(self) -> str:
        return self.label or f"{self.tool}({self.id})"


@dataclass(frozen=True)
class Synthesis:
    """The final LLM step. Optional - a workflow can be tools only."""

    prompt: str
    system: str = (
        "You are a research assistant for a market terminal. You will be given "
        "a table of measured facts, each with an id like [f3].\n\n"
        "Rules:\n"
        "1. Every number you write MUST be immediately followed by the id of "
        "the fact it came from, e.g. \"closed at $182.40 [f1]\".\n"
        "2. Never state a number that is not in the fact table. If something "
        "was not measured, say so in words instead.\n"
        "3. Be concise and descriptive. Do not give investment advice.\n"
        "4. If the facts are thin, say what is missing rather than filling gaps."
    )
    label: str = "Synthesis"


@dataclass(frozen=True)
class Workflow:
    """A named DAG plus an optional synthesis step."""

    key: str
    name: str
    description: str
    steps: Sequence[Step]
    synthesis: Optional[Synthesis] = None
    inputs: Sequence[str] = field(default_factory=tuple)

    def validate(self) -> None:
        """Fail loudly on a malformed definition, before anything runs."""
        seen: set = set()
        for step in self.steps:
            if step.id in seen:
                raise ValueError(f"duplicate step id {step.id!r}")
            seen.add(step.id)
            get_spec(step.tool)          # raises if the tool is unknown
        for step in self.steps:
            for dep in step.depends_on:
                if dep not in seen:
                    raise ValueError(f"step {step.id!r} depends on unknown {dep!r}")
        _order(self.steps)               # raises on a cycle


# ==============================================================================
# RUN RECORD
# ==============================================================================


@dataclass
class Run:
    """Everything that happened, and enough of it to replay and audit."""

    run_id: str
    workflow_key: str
    workflow_name: str
    inputs: Dict[str, Any]
    status: str = PENDING
    started_at: float = 0.0
    finished_at: float = 0.0
    step_status: Dict[str, str] = field(default_factory=dict)
    results: Dict[str, ToolResult] = field(default_factory=dict)
    ledger: Ledger = field(default_factory=Ledger)
    memo: Optional[str] = None
    verification: Optional[VerificationReport] = None
    error: Optional[str] = None
    model: str = ""

    @property
    def duration_ms(self) -> float:
        if not self.finished_at:
            return 0.0
        return (self.finished_at - self.started_at) * 1000.0

    @property
    def failed_steps(self) -> List[str]:
        return [k for k, v in self.step_status.items() if v == FAILED]

    def to_json(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workflow_key": self.workflow_key,
            "workflow_name": self.workflow_name,
            "inputs": self.inputs,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": round(self.duration_ms, 2),
            "model": self.model,
            "step_status": self.step_status,
            "results": {k: v.to_json() for k, v in self.results.items()},
            "facts": self.ledger.to_json(),
            "memo": self.memo,
            "verification": self.verification.to_json() if self.verification else None,
            "error": self.error,
        }


# ==============================================================================
# EXECUTION
# ==============================================================================


def _order(steps: Sequence[Step]) -> List[List[Step]]:
    """Group steps into dependency levels. Steps in a level can run together."""
    by_id = {s.id: s for s in steps}
    remaining = dict(by_id)
    done: set = set()
    levels: List[List[Step]] = []

    while remaining:
        ready = [s for s in remaining.values()
                 if all(d in done for d in s.depends_on)]
        if not ready:
            raise ValueError(
                f"cyclic or unsatisfiable dependencies among: {sorted(remaining)}"
            )
        levels.append(ready)
        for step in ready:
            done.add(step.id)
            remaining.pop(step.id)
    return levels


def _resolve(value: Any, inputs: Dict[str, Any], results: Dict[str, ToolResult]) -> Any:
    """Expand ``$input`` / ``$artifact`` / ``$value`` references."""
    if isinstance(value, list):
        return [_resolve(v, inputs, results) for v in value]
    if isinstance(value, dict):
        return {k: _resolve(v, inputs, results) for k, v in value.items()}
    if not isinstance(value, str) or not value.startswith("$"):
        return value

    if value.startswith("$input."):
        return inputs.get(value[len("$input."):])

    if value.startswith("$artifact:"):
        result = results.get(value[len("$artifact:"):])
        return result.artifact if result else None

    if value.startswith("$value:"):
        path = value[len("$value:"):]
        step_id, _, field_path = path.partition(".")
        result = results.get(step_id)
        if result is None or not result.ok:
            return None
        current: Any = result.value
        for part in filter(None, field_path.split(".")):
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    return value


def execute(
    workflow: Workflow,
    inputs: Optional[Dict[str, Any]] = None,
    llm: Optional[Callable[[str, str], str]] = None,
    model: str = "",
    on_event: Optional[Callable[[str, str, Any], None]] = None,
    max_workers: int = 4,
) -> Run:
    """Run *workflow* and return the complete record.

    *llm* is injected as ``fn(prompt, system) -> str`` so the engine has no
    provider dependency and the tests need no network. If it is ``None`` and the
    workflow has a synthesis step, the run completes with facts but no memo,
    reported honestly rather than filled in.

    *on_event* receives ``(kind, step_id, payload)`` for live UI updates.
    """
    workflow.validate()
    inputs = dict(inputs or {})

    run = Run(
        run_id=f"r{uuid.uuid4().hex[:10]}",
        workflow_key=workflow.key,
        workflow_name=workflow.name,
        inputs=inputs,
        status=RUNNING,
        started_at=time.time(),
        model=model,
    )
    for step in workflow.steps:
        run.step_status[step.id] = PENDING

    def emit(kind: str, step_id: str = "", payload: Any = None) -> None:
        if on_event:
            try:
                on_event(kind, step_id, payload)
            except Exception:  # noqa: BLE001 - a broken listener must not fail the run
                pass

    emit("run_started", "", run.run_id)

    halted = False
    for level in _order(workflow.steps):
        if halted:
            for step in level:
                run.step_status[step.id] = SKIPPED
                emit("step_skipped", step.id)
            continue

        # A dependency that failed makes its dependents unrunnable, regardless
        # of whether the run as a whole halted.
        runnable, blocked = [], []
        for step in level:
            if any(run.step_status.get(d) != OK for d in step.depends_on):
                blocked.append(step)
            else:
                runnable.append(step)

        for step in blocked:
            run.step_status[step.id] = SKIPPED
            emit("step_skipped", step.id)

        for step in runnable:
            run.step_status[step.id] = RUNNING
            emit("step_started", step.id)

        def invoke(step: Step) -> ToolResult:
            args = _resolve(dict(step.args), inputs, run.results)
            args = {k: v for k, v in args.items() if v is not None}
            return call(step.tool, args)

        if len(runnable) == 1:
            outcomes = [(runnable[0], invoke(runnable[0]))]
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                outcomes = list(zip(runnable, pool.map(invoke, runnable)))

        for step, result in outcomes:
            run.results[step.id] = result
            if result.ok:
                run.step_status[step.id] = OK
                run.ledger.add_from_result(result, prefix=step.id)
                emit("step_ok", step.id, result)
            else:
                run.step_status[step.id] = FAILED
                emit("step_failed", step.id, result)
                if step.required:
                    halted = True
                    run.error = (
                        f"required step {step.display()!r} failed: {result.error}"
                    )

    if halted:
        run.status = FAILED
        run.finished_at = time.time()
        emit("run_failed", "", run.error)
        return run

    # ---- synthesis ------------------------------------------------------
    if workflow.synthesis is not None:
        if llm is None:
            run.status = OK
            run.error = "no language model configured; facts collected, memo not written"
            run.finished_at = time.time()
            emit("run_finished", "", run)
            return run

        prompt = (
            f"{workflow.synthesis.prompt.strip()}\n\n"
            f"Inputs: {inputs}\n\n"
            f"Measured facts:\n{run.ledger.render_table()}\n"
        )
        emit("synthesis_started", "synthesis")
        try:
            memo = llm(prompt, workflow.synthesis.system)
        except Exception as exc:  # noqa: BLE001
            run.status = FAILED
            run.error = f"synthesis failed: {type(exc).__name__}: {exc}"
            run.finished_at = time.time()
            emit("run_failed", "synthesis", run.error)
            return run

        if not memo or not memo.strip():
            run.status = FAILED
            run.error = "synthesis returned nothing"
            run.finished_at = time.time()
            emit("run_failed", "synthesis", run.error)
            return run

        run.memo = memo
        run.verification = verify(memo, run.ledger)
        emit("synthesis_ok", "synthesis", run.verification)

    run.status = OK
    run.finished_at = time.time()
    emit("run_finished", "", run)
    return run
