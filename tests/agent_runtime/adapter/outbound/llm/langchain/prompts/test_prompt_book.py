import pytest

from agent_runtime.adapter.outbound.llm.langchain.prompts.generic_prompts import (
    GENERIC_PROMPTS,
    prompt_book,
)
from agent_runtime.adapter.outbound.llm.langchain.prompts.prompt_book import (
    PromptBook,
    SystemTemplate,
)
from agent_runtime.domain.agent.agent_prompts import AgentPrompts
from agent_runtime.domain.workflow.step import Step


def test_a_step_without_an_agent_prompt_uses_the_generic_one_with_the_agent_s_identity() -> None:
    book = prompt_book("the observation agent")

    prompt = book.system(Step.UNDERSTAND, output_format="SCHEMA")

    assert prompt.startswith("You classify the user's latest message for the observation agent.")
    assert "SCHEMA" in prompt


def test_an_agent_prompt_replaces_the_generic_one_for_its_step_only() -> None:
    book = prompt_book("chat", AgentPrompts({Step.ACT: "Be {identity}.\n{mode}"}))

    assert book.system(Step.ACT, mode="MODE", request="q") == "Be chat.\nMODE"
    assert "You classify" in book.system(Step.UNDERSTAND, output_format="SCHEMA")


def test_an_unknown_placeholder_is_refused_and_the_known_ones_are_listed() -> None:
    prompts = AgentPrompts({Step.PLAN: "{tools} {output_format} {mood}"})

    with pytest.raises(
        ValueError, match=r"agent's plan prompt uses \{mood\}; it may use .*\{task\}"
    ):
        prompt_book("planner", prompts)


def test_a_prompt_without_what_its_step_needs_is_refused() -> None:
    prompts = AgentPrompts({Step.UNDERSTAND: "Classify the message."})

    with pytest.raises(ValueError, match=r"must use \{output_format\}"):
        prompt_book("classifier", prompts)


def test_a_prompt_for_a_step_the_book_has_no_template_for_is_refused() -> None:
    defaults = {Step.ACT: GENERIC_PROMPTS[Step.ACT]}

    with pytest.raises(ValueError, match="no system prompt is used for plan"):
        PromptBook("x", defaults, AgentPrompts({Step.PLAN: "{tools} {output_format}"}))


def test_a_generic_template_is_checked_when_it_is_defined() -> None:
    with pytest.raises(ValueError, match=r"generic prompt uses \{oops\}"):
        SystemTemplate("{oops}", known=frozenset())


def test_every_prompted_step_has_a_generic_prompt() -> None:
    assert set(GENERIC_PROMPTS) == {
        Step.UNDERSTAND,
        Step.PLAN,
        Step.ACT,
        Step.REVIEW,
        Step.SCREEN,
        Step.SUMMARIZE,
    }
