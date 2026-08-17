"""Tests for workflow/tools.py.

The load-bearing property is that a tool failure is *data*, not an exception:
the engine has to be able to record that something was attempted and did not
work, because a failed fetch is what makes a claim unstatable later.
"""

import pytest

from workflow import tools


@pytest.fixture(autouse=True)
def clean_registry():
    """Each test gets its own registry so registrations don't leak."""
    saved = dict(tools.REGISTRY)
    tools.REGISTRY.clear()
    yield
    tools.REGISTRY.clear()
    tools.REGISTRY.update(saved)


def _register_ok():
    @tools.tool("adder", "adds", {"a": {"type": "number", "required": True},
                                  "b": {"type": "number", "required": False}},
                source="computed")
    def _adder(a, b=0):
        return {"sum": a + b}


# ==============================================================================
# Registration
# ==============================================================================


def test_tool_registers_and_is_listed():
    _register_ok()
    assert "adder" in tools.REGISTRY
    assert [s.name for s in tools.list_tools()] == ["adder"]


def test_duplicate_registration_is_rejected():
    _register_ok()
    with pytest.raises(ValueError):
        _register_ok()


def test_unknown_tool_raises_because_the_workflow_is_malformed():
    # A bad tool *name* is a bug in the workflow definition, not a runtime
    # data problem, so it must not be swallowed into ok=False.
    with pytest.raises(KeyError):
        tools.call("nope")


def test_schema_lists_required_params():
    _register_ok()
    schema = tools.get_spec("adder").to_schema()
    assert schema["parameters"]["required"] == ["a"]
    assert "b" in schema["parameters"]["properties"]


# ==============================================================================
# Invocation
# ==============================================================================


def test_successful_call_records_provenance():
    _register_ok()
    result = tools.call("adder", {"a": 2, "b": 3})
    assert result.ok
    assert result.value == {"sum": 5}
    assert result.source == "computed"
    assert result.fetched_at > 0
    assert result.duration_ms >= 0
    assert result.call_id.startswith("t")


def test_missing_required_argument_is_a_failed_result_not_an_exception():
    _register_ok()
    result = tools.call("adder", {})
    assert result.ok is False
    assert result.value is None
    assert "missing required argument" in result.error


def test_exception_inside_a_tool_becomes_a_failed_result():
    @tools.tool("boom", "raises", {})
    def _boom():
        raise ValueError("upstream is down")

    result = tools.call("boom")
    assert result.ok is False
    assert result.value is None
    assert "ValueError" in result.error
    assert "upstream is down" in result.error


def test_failed_result_still_carries_timing_and_source():
    @tools.tool("boom", "raises", {}, source="yfinance")
    def _boom():
        raise RuntimeError("x")

    result = tools.call("boom")
    assert result.source == "yfinance"
    assert result.fetched_at > 0


def test_explicit_call_id_is_honoured():
    _register_ok()
    assert tools.call("adder", {"a": 1}, call_id="t42").call_id == "t42"


def test_call_ids_are_unique():
    _register_ok()
    ids = {tools.call("adder", {"a": 1}).call_id for _ in range(50)}
    assert len(ids) == 50


# ==============================================================================
# Artifacts and serialization
# ==============================================================================


def test_artifact_is_separated_from_value():
    heavy = object()

    @tools.tool("withartifact", "returns a heavy object", {})
    def _fn():
        return {"rows": 3}, heavy

    result = tools.call("withartifact")
    assert result.value == {"rows": 3}
    assert result.artifact is heavy


def test_artifact_is_never_persisted():
    """Run records go to disk; a DataFrame must not."""
    heavy = object()

    @tools.tool("withartifact", "returns a heavy object", {})
    def _fn():
        return {"rows": 3}, heavy

    payload = tools.call("withartifact").to_json()
    assert "artifact" not in payload
    assert payload["value"] == {"rows": 3}


def test_result_survives_a_json_round_trip():
    _register_ok()
    original = tools.call("adder", {"a": 2, "b": 3})
    restored = tools.ToolResult.from_json(original.to_json())
    assert restored.call_id == original.call_id
    assert restored.tool == original.tool
    assert restored.value == original.value
    assert restored.ok is True


def test_failed_result_survives_a_json_round_trip():
    @tools.tool("boom", "raises", {})
    def _boom():
        raise ValueError("nope")

    restored = tools.ToolResult.from_json(tools.call("boom").to_json())
    assert restored.ok is False
    assert "nope" in restored.error


def test_a_plain_tuple_return_is_not_mistaken_for_an_artifact():
    @tools.tool("pair", "returns a real tuple", {})
    def _fn():
        return (1, 2)

    assert tools.call("pair").value == (1, 2)
