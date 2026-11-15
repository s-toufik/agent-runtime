from collections.abc import Mapping
from types import MappingProxyType

from agent_runtime.adapter.outbound.llm.langchain.prompts import (
    act,
    context,
    guard,
    plan,
    review,
    summary,
)
from agent_runtime.adapter.outbound.llm.langchain.prompts.prompt_book import (
    PromptBook,
    SystemTemplate,
)
from agent_runtime.domain.agent.agent_prompts import AgentPrompts
from agent_runtime.domain.workflow.step import Step

GENERIC_PROMPTS: Mapping[Step, SystemTemplate] = MappingProxyType(
    {
        Step.UNDERSTAND: context.SYSTEM,
        Step.PLAN: plan.SYSTEM,
        Step.ACT: act.SYSTEM,
        Step.REVIEW: review.SYSTEM,
        Step.SCREEN: guard.SYSTEM,
        Step.SUMMARIZE: summary.SYSTEM,
    }
)


def prompt_book(identity: str, prompts: AgentPrompts | None = None) -> PromptBook:
    return PromptBook(identity, GENERIC_PROMPTS, prompts)
