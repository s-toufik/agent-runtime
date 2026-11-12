from langchain_core.messages import HumanMessage
from pycraftcore.logger.port import Logger

from agent_runtime.adapter.outbound.llm.langchain.chat_models import ChatModels
from agent_runtime.adapter.outbound.llm.langchain.context_window import ContextWindow, input_budget
from agent_runtime.adapter.outbound.llm.langchain.messages import from_work, to_draft
from agent_runtime.adapter.outbound.llm.langchain.plan_request import (
    REQUEST_PLAN_TOOL,
    direct_draft,
)
from agent_runtime.adapter.outbound.llm.langchain.prompts.act import (
    act_system_prompt,
    next_step_request,
)
from agent_runtime.adapter.outbound.llm.langchain.reply.reply_reader import ReplyReader
from agent_runtime.adapter.outbound.llm.model_catalog import AgentRole
from agent_runtime.domain.conversation.conversation import Conversation
from agent_runtime.domain.tool.tool_specification import ToolSpecification
from agent_runtime.domain.turn.draft import Draft
from agent_runtime.domain.turn.plan_progress import PlanProgress
from agent_runtime.domain.turn.turn import Turn


class LangChainActor:
    def __init__(
        self,
        models: ChatModels,
        window: ContextWindow,
        logger: Logger,
        reply: ReplyReader,
        final_reply: ReplyReader,
    ) -> None:
        self._models = models
        self._window = window
        self._logger = logger
        self._reply = reply
        self._final_reply = final_reply

    async def act(
        self, conversation: Conversation, turn: Turn, tools: list[ToolSpecification]
    ) -> Draft:
        progress = turn.progress
        system = act_system_prompt(turn.query, progress, tools, turn.prior)
        tail = [HumanMessage(content=turn.request), *from_work(turn.work)]
        next_step = next_step_request(progress) if progress else None
        if next_step:
            tail.append(HumanMessage(content=next_step))
        bound: list[dict] = (
            [REQUEST_PLAN_TOOL] if progress is None else _plan_tools(progress, tools)
        )
        settings = turn.settings
        budget: int = input_budget(settings.context_tokens, settings.output_tokens, bound)
        messages = self._window.build(system, conversation, budget, tail)
        model = self._models.for_role(AgentRole.ACT, turn.model)
        self._logger.debug(f"Calling the act model (step {turn.steps_taken + 1})")
        if progress is None:
            reader = self._final_reply if turn.is_plain_direct_answer else self._reply
            reply = await reader.read(model.bind_tools(bound), messages)
            return direct_draft(to_draft(reply))
        if bound:
            model = model.bind_tools(bound)
        return to_draft(await self._reply.read(model, messages))


def _plan_tools(progress: PlanProgress, tools: list[ToolSpecification]) -> list[dict]:
    named: set[str] = {step.tool for step in progress.plan.steps if step.tool}
    return [_tool(spec) for spec in tools if spec.name in named]


def _tool(specification: ToolSpecification) -> dict:
    return {
        "name": specification.name,
        "description": specification.description,
        "parameters": specification.parameters,
    }
