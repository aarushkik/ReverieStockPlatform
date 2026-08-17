"""
The tool registry: every action a workflow can take on real data.

A tool is a thin, typed wrapper over an existing function. It always returns a
:class:`ToolResult` - never a bare value and never an exception - so the engine
can record what was attempted, what came back, how long it took and where it
came from, whether or not it worked.

Three properties this layer guarantees, because everything downstream depends
on them:

**A failed tool returns ``ok=False``, never a substitute.** This is the whole
premise. If a workflow cannot get a price, the memo must be unable to state a
price. See ``marketdata.py`` for the fetchers this relies on.

**Every result is addressable.** Each call gets an id (``t3``) that survives
into the fact ledger, the citation in the model's prose, and the run record on
disk. A number in a finished memo can be traced back to the exact call,
provider and timestamp that produced it.

**Results are JSON-serializable.** Runs are persisted and replayed, so
``value`` holds only plain types. A tool that also produces something heavy - a
price DataFrame the next step needs - puts it in ``artifact``, which is passed
in-process and deliberately not written to disk.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

__all__ = [
    "ToolResult",
    "ToolSpec",
    "REGISTRY",
    "tool",
    "call",
    "get_spec",
    "list_tools",
]


# ==============================================================================
# RESULT
# ==============================================================================


@dataclass
class ToolResult:
    """The outcome of one tool invocation."""

    call_id: str
    tool: str
    args: Dict[str, Any]
    ok: bool
    value: Any = None
    error: Optional[str] = None
    source: str = ""
    fetched_at: float = 0.0
    duration_ms: float = 0.0

    # Heavy in-process payload (e.g. a DataFrame) for downstream steps. Never
    # serialized into the run record.
    artifact: Any = field(default=None, repr=False, compare=False)

    def to_json(self) -> Dict[str, Any]:
        """The persisted form. Excludes ``artifact`` by design."""
        return {
            "call_id": self.call_id,
            "tool": self.tool,
            "args": self.args,
            "ok": self.ok,
            "value": self.value,
            "error": self.error,
            "source": self.source,
            "fetched_at": self.fetched_at,
            "duration_ms": round(self.duration_ms, 2),
        }

    @classmethod
    def from_json(cls, payload: Dict[str, Any]) -> "ToolResult":
        known = {
            k: payload.get(k)
            for k in ("call_id", "tool", "args", "ok", "value", "error",
                      "source", "fetched_at", "duration_ms")
        }
        known["args"] = known.get("args") or {}
        known["ok"] = bool(known.get("ok"))
        known["duration_ms"] = float(known.get("duration_ms") or 0.0)
        known["fetched_at"] = float(known.get("fetched_at") or 0.0)
        return cls(**known)


# ==============================================================================
# REGISTRY
# ==============================================================================


@dataclass(frozen=True)
class ToolSpec:
    """Declaration of a callable tool."""

    name: str
    description: str
    params: Dict[str, Dict[str, Any]]   # param -> {type, required, description}
    fn: Callable[..., Any]
    source: str                          # provider label recorded on results

    def required_params(self) -> List[str]:
        return [p for p, meta in self.params.items() if meta.get("required")]

    def to_schema(self) -> Dict[str, Any]:
        """JSON-schema-ish description, for the builder UI and agentic mode."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    name: {
                        "type": meta.get("type", "string"),
                        "description": meta.get("description", ""),
                    }
                    for name, meta in self.params.items()
                },
                "required": self.required_params(),
            },
        }


REGISTRY: Dict[str, ToolSpec] = {}


def tool(name: str, description: str, params: Dict[str, Dict[str, Any]],
         source: str = "computed") -> Callable:
    """Register a function as a workflow tool."""

    def decorator(fn: Callable) -> Callable:
        if name in REGISTRY:
            raise ValueError(f"tool {name!r} is already registered")
        REGISTRY[name] = ToolSpec(
            name=name, description=description, params=params, fn=fn, source=source
        )
        return fn

    return decorator


def get_spec(name: str) -> ToolSpec:
    if name not in REGISTRY:
        raise KeyError(f"unknown tool {name!r}; known: {sorted(REGISTRY)}")
    return REGISTRY[name]


def list_tools() -> List[ToolSpec]:
    return [REGISTRY[k] for k in sorted(REGISTRY)]


# ==============================================================================
# INVOCATION
# ==============================================================================


def _new_call_id() -> str:
    return f"t{uuid.uuid4().hex[:8]}"


def call(name: str, args: Optional[Dict[str, Any]] = None,
         call_id: Optional[str] = None) -> ToolResult:
    """Invoke a tool, capturing success or failure uniformly.

    Never raises for a tool-level failure: a missing provider, a bad symbol or
    an exception inside the tool all come back as ``ok=False`` with an error
    string. An unknown *tool name*, by contrast, is a programming error in the
    workflow definition and does raise.
    """
    spec = get_spec(name)           # raises: the workflow itself is malformed
    args = dict(args or {})
    call_id = call_id or _new_call_id()

    missing = [p for p in spec.required_params() if p not in args]
    if missing:
        return ToolResult(
            call_id=call_id, tool=name, args=args, ok=False,
            error=f"missing required argument(s): {', '.join(missing)}",
            source=spec.source, fetched_at=time.time(),
        )

    started = time.perf_counter()
    try:
        value = spec.fn(**args)
    except Exception as exc:  # noqa: BLE001 - uniform capture is the point
        return ToolResult(
            call_id=call_id, tool=name, args=args, ok=False,
            error=f"{type(exc).__name__}: {exc}",
            source=spec.source, fetched_at=time.time(),
            duration_ms=(time.perf_counter() - started) * 1000.0,
        )

    duration = (time.perf_counter() - started) * 1000.0

    # A tool may return (value, artifact) to hand a heavy object downstream
    # without it entering the persisted record.
    artifact = None
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], dict):
        value, artifact = value

    return ToolResult(
        call_id=call_id, tool=name, args=args, ok=True, value=value,
        source=spec.source, fetched_at=time.time(), duration_ms=duration,
        artifact=artifact,
    )
