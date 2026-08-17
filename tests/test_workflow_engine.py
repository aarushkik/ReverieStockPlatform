"""Tests for workflow/engine.py.

All tools here are fakes. The engine's contract is about orchestration and
failure propagation, and the most important property — that a failed required
step means no memo is written — must be provable without a network.
"""

import pytest

from workflow import engine, tools
from workflow.engine import OK, FAILED, SKIPPED, Step, Synthesis, Workflow, execute


@pytest.fixture(autouse=True)
def sandbox_registry():
    saved = dict(tools.REGISTRY)
    tools.REGISTRY.clear()

    @tools.tool("echo", "returns its argument", {"v": {"type": "number", "required": True}})
    def _echo(v):
        return {"v": v}

    @tools.tool("boom", "always fails", {})
    def _boom():
        raise RuntimeError("provider down")

    @tools.tool("heavy", "returns an artifact", {})
    def _heavy():
        return {"rows": 2}, ["ARTIFACT"]

    @tools.tool("consume", "consumes an artifact", {"payload": {"type": "object", "required": True}})
    def _consume(payload):
        return {"received": len(payload)}

    yield
    tools.REGISTRY.clear()
    tools.REGISTRY.update(saved)


def _wf(steps, synthesis=None, key="t"):
    return Workflow(key=key, name="Test", description="", steps=tuple(steps),
                    synthesis=synthesis)


# ==============================================================================
# Validation
# ==============================================================================


def test_unknown_tool_is_rejected_before_anything_runs():
    with pytest.raises(KeyError):
        _wf([Step("a", "nosuchtool")]).validate()


def test_duplicate_step_ids_are_rejected():
    with pytest.raises(ValueError):
        _wf([Step("a", "echo", {"v": 1}), Step("a", "echo", {"v": 2})]).validate()


def test_dependency_on_an_unknown_step_is_rejected():
    with pytest.raises(ValueError):
        _wf([Step("a", "echo", {"v": 1}, depends_on=("ghost",))]).validate()


def test_a_cycle_is_rejected():
    workflow = _wf([
        Step("a", "echo", {"v": 1}, depends_on=("b",)),
        Step("b", "echo", {"v": 2}, depends_on=("a",)),
    ])
    with pytest.raises(ValueError):
        workflow.validate()


# ==============================================================================
# Ordering
# ==============================================================================


def test_independent_steps_share_a_level():
    levels = engine._order([Step("a", "echo"), Step("b", "echo")])
    assert len(levels) == 1


def test_dependencies_create_levels():
    levels = engine._order([
        Step("a", "echo"),
        Step("b", "echo", depends_on=("a",)),
        Step("c", "echo", depends_on=("b",)),
    ])
    assert [[s.id for s in level] for level in levels] == [["a"], ["b"], ["c"]]


def test_a_diamond_resolves_correctly():
    levels = engine._order([
        Step("root", "echo"),
        Step("left", "echo", depends_on=("root",)),
        Step("right", "echo", depends_on=("root",)),
        Step("join", "echo", depends_on=("left", "right")),
    ])
    assert [s.id for s in levels[0]] == ["root"]
    assert sorted(s.id for s in levels[1]) == ["left", "right"]
    assert [s.id for s in levels[2]] == ["join"]


# ==============================================================================
# Reference resolution
# ==============================================================================


def test_input_reference_resolves():
    run = execute(_wf([Step("a", "echo", {"v": "$input.n"})]), {"n": 7})
    assert run.results["a"].value == {"v": 7}


def test_artifact_reference_passes_the_heavy_object():
    workflow = _wf([
        Step("h", "heavy"),
        Step("c", "consume", {"payload": "$artifact:h"}, depends_on=("h",)),
    ])
    run = execute(workflow)
    assert run.results["c"].value == {"received": 1}


def test_value_reference_reads_a_field():
    workflow = _wf([
        Step("a", "echo", {"v": 5}),
        Step("b", "echo", {"v": "$value:a.v"}, depends_on=("a",)),
    ])
    run = execute(workflow)
    assert run.results["b"].value == {"v": 5}


def test_value_reference_to_a_failed_step_is_none():
    assert engine._resolve("$value:missing.x", {}, {}) is None


# ==============================================================================
# Failure propagation — the central behaviour
# ==============================================================================


def test_a_required_failure_halts_the_run():
    run = execute(_wf([Step("a", "boom"), Step("b", "echo", {"v": 1}, depends_on=("a",))]))
    assert run.status == FAILED
    assert run.step_status["a"] == FAILED
    assert run.step_status["b"] == SKIPPED
    assert "provider down" in run.error


def test_no_memo_is_written_when_a_required_step_fails():
    """The demo moment: the engine would rather say nothing."""
    workflow = _wf([Step("a", "boom")], synthesis=Synthesis(prompt="write something"))
    run = execute(workflow, llm=lambda p, s: "The price is $100.00 [f1].")
    assert run.status == FAILED
    assert run.memo is None
    assert run.verification is None


def test_an_optional_failure_does_not_halt_the_run():
    workflow = _wf([
        Step("a", "boom", required=False),
        Step("b", "echo", {"v": 1}),
    ])
    run = execute(workflow)
    assert run.status == OK
    assert run.step_status["a"] == FAILED
    assert run.step_status["b"] == OK


def test_dependents_of_an_optional_failure_are_skipped():
    workflow = _wf([
        Step("a", "boom", required=False),
        Step("b", "echo", {"v": "$value:a.v"}, depends_on=("a",), required=False),
    ])
    run = execute(workflow)
    assert run.step_status["b"] == SKIPPED


def test_a_failed_step_contributes_no_facts():
    run = execute(_wf([Step("a", "boom", required=False), Step("b", "echo", {"v": 3})]))
    labels = [f.label for f in run.ledger.facts]
    assert labels == ["b.v"]


# ==============================================================================
# Synthesis
# ==============================================================================


def _one_fact_workflow(prompt="write"):
    return _wf([Step("a", "echo", {"v": 42})], synthesis=Synthesis(prompt=prompt))


def test_synthesis_output_is_verified():
    run = execute(_one_fact_workflow(), llm=lambda p, s: "The value is 42 [f1].")
    assert run.status == OK
    assert run.verification.verified == 1
    assert run.verification.pass_rate == 1.0


def test_a_hallucinated_number_is_flagged_not_hidden():
    run = execute(_one_fact_workflow(), llm=lambda p, s: "The value is 999 [f1].")
    assert run.status == OK          # the run succeeded
    assert run.verification.flagged[0].status == "mismatch"   # the claim did not


def test_the_fact_table_reaches_the_prompt():
    captured = {}

    def spy(prompt, system):
        captured["prompt"] = prompt
        captured["system"] = system
        return "42 [f1]"

    execute(_one_fact_workflow(), llm=spy)
    assert "[f1]" in captured["prompt"]
    assert "a.v" in captured["prompt"]
    assert "MUST be immediately followed" in captured["system"]


def test_no_llm_means_no_memo_but_not_a_failed_run():
    run = execute(_one_fact_workflow(), llm=None)
    assert run.status == OK
    assert run.memo is None
    assert "no language model" in run.error


def test_an_llm_exception_fails_the_run_without_a_memo():
    def broken(prompt, system):
        raise ConnectionError("model unreachable")

    run = execute(_one_fact_workflow(), llm=broken)
    assert run.status == FAILED
    assert run.memo is None
    assert "model unreachable" in run.error


@pytest.mark.parametrize("reply", ["", "   ", "\n"])
def test_an_empty_model_reply_fails_rather_than_shipping_a_blank_memo(reply):
    run = execute(_one_fact_workflow(), llm=lambda p, s: reply)
    assert run.status == FAILED
    assert run.memo is None


def test_a_workflow_without_synthesis_completes_cleanly():
    run = execute(_wf([Step("a", "echo", {"v": 1})]))
    assert run.status == OK
    assert run.memo is None
    assert run.error is None


# ==============================================================================
# Events and the run record
# ==============================================================================


def test_events_describe_the_lifecycle():
    seen = []
    execute(_one_fact_workflow(), llm=lambda p, s: "42 [f1]",
            on_event=lambda kind, step, payload: seen.append(kind))
    assert seen[0] == "run_started"
    assert "step_ok" in seen
    assert "synthesis_ok" in seen
    assert seen[-1] == "run_finished"


def test_a_broken_event_listener_cannot_fail_the_run():
    def bad_listener(kind, step, payload):
        raise RuntimeError("ui blew up")

    run = execute(_wf([Step("a", "echo", {"v": 1})]), on_event=bad_listener)
    assert run.status == OK


def test_run_serializes_completely():
    run = execute(_one_fact_workflow(), llm=lambda p, s: "42 [f1]", model="test-model")
    payload = run.to_json()
    assert payload["status"] == OK
    assert payload["model"] == "test-model"
    assert payload["memo"] == "42 [f1]"
    assert payload["verification"]["verified"] == 1
    assert len(payload["facts"]) == 1
    assert "a" in payload["results"]
    assert payload["duration_ms"] >= 0


def test_run_ids_are_unique():
    ids = {execute(_wf([Step("a", "echo", {"v": 1})])).run_id for _ in range(20)}
    assert len(ids) == 20
