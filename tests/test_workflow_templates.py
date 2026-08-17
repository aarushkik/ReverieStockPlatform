"""Tests for the shipped workflow templates.

Deliberately in its own file: these run against the *real* tool registry, so
they also assert that every template references tools that actually exist. The
engine tests sandbox the registry and would hide that.
"""

import pytest

import workflow


def test_templates_are_registered():
    keys = {t.key for t in workflow.list_templates()}
    assert {"due_diligence", "why_move", "disconfirm", "portfolio_brief"} <= keys


def test_every_template_is_structurally_valid():
    """Catches a template referencing a tool that was renamed or removed."""
    for template in workflow.list_templates():
        template.validate()


def test_every_template_is_described_and_declares_inputs():
    for template in workflow.list_templates():
        assert template.inputs, f"{template.key} declares no inputs"
        assert template.name, f"{template.key} has no name"
        assert template.description, f"{template.key} has no description"


def test_every_step_references_a_registered_tool():
    known = {spec.name for spec in workflow.list_tools()}
    for template in workflow.list_templates():
        for step in template.steps:
            assert step.tool in known, f"{template.key}.{step.id} -> {step.tool}"


def test_step_arguments_only_reference_declared_inputs_or_earlier_steps():
    """A '$input.foo' that the template never declares would silently resolve
    to None and the step would run with a missing argument."""
    for template in workflow.list_templates():
        step_ids = {s.id for s in template.steps}
        for step in template.steps:
            for value in step.args.values():
                if not isinstance(value, str) or not value.startswith("$"):
                    continue
                if value.startswith("$input."):
                    assert value[len("$input."):] in template.inputs, (
                        f"{template.key}.{step.id} uses undeclared input {value}")
                elif value.startswith("$artifact:"):
                    assert value[len("$artifact:"):] in step_ids
                elif value.startswith("$value:"):
                    assert value[len("$value:"):].split(".")[0] in step_ids


def test_steps_that_consume_another_step_declare_the_dependency():
    """A reference without a depends_on would race: the engine could run the
    consumer in the same level as the producer."""
    for template in workflow.list_templates():
        for step in template.steps:
            for value in step.args.values():
                if not isinstance(value, str):
                    continue
                producer = None
                if value.startswith("$artifact:"):
                    producer = value[len("$artifact:"):]
                elif value.startswith("$value:"):
                    producer = value[len("$value:"):].split(".")[0]
                if producer:
                    assert producer in step.depends_on, (
                        f"{template.key}.{step.id} reads {producer} "
                        f"but does not depend on it")


def test_synthesis_prompts_do_not_solicit_advice():
    """The engine can guarantee a number was measured. It cannot guarantee a
    recommendation built on those numbers is sound, so the templates stay
    descriptive."""
    banned = ("buy", "sell", "recommend", "price target", "should you")
    for template in workflow.list_templates():
        if template.synthesis is None:
            continue
        prompt = template.synthesis.prompt.lower()
        for word in banned:
            # "Do not give a recommendation" is fine; soliciting one is not.
            if word in prompt:
                assert "do not" in prompt or "not give" in prompt, (
                    f"{template.key} synthesis solicits {word!r}")


def test_due_diligence_downloads_prices_once():
    """The analytical steps must reuse the fetched history rather than each
    triggering their own download."""
    template = workflow.get_template("due_diligence")
    price_steps = [s for s in template.steps if s.tool == "prices"]
    assert len(price_steps) == 1

    for step_id in ("indicators", "patterns"):
        step = next(s for s in template.steps if s.id == step_id)
        assert step.args.get("history") == "$artifact:prices"


def test_optional_steps_are_the_ones_that_can_be_missing():
    """A news outage should not stop a due-diligence run; a price outage should."""
    template = workflow.get_template("due_diligence")
    by_id = {s.id: s for s in template.steps}
    assert by_id["prices"].required is True
    assert by_id["news"].required is False
    assert by_id["fundamentals"].required is False


@pytest.mark.parametrize("key", ["due_diligence", "why_move", "disconfirm"])
def test_single_symbol_templates_take_a_symbol(key):
    assert "symbol" in workflow.get_template(key).inputs


def test_unknown_template_raises():
    with pytest.raises(KeyError):
        workflow.get_template("nope")
