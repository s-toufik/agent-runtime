from langchain_core.messages import HumanMessage, SystemMessage
from pycraftcore.logger.port import Logger

from agent_orchestrator.adapter.outbound.llm.langchain.chat_models import ChatModels
from agent_orchestrator.adapter.outbound.llm.langchain.dto import ScreeningDto
from agent_orchestrator.adapter.outbound.llm.langchain.model_call import invoke_structured
from agent_orchestrator.adapter.outbound.llm.langchain.prompts.guard import (
    guard_request,
    guard_system_prompt,
)
from agent_orchestrator.adapter.outbound.llm.model_catalog import AgentRole
from agent_orchestrator.domain.conversation.conversation import Conversation
from agent_orchestrator.domain.turn.plan import Plan
from agent_orchestrator.domain.turn.screening import Screening
from agent_orchestrator.domain.turn.turn import Turn


class LangChainGuard:
    def __init__(self, model: ChatModels, logger: Logger):
        self._model = model
        self._logger = logger

    async def screen(self, conversation: Conversation, turn: Turn, plan: Plan) -> Screening | None:
        messages = [
            SystemMessage(content=guard_system_prompt(ScreeningDto.model_json_schema())),
            HumanMessage(content=guard_request(request=turn.query, plan=plan.render())),
        ]
        self._logger.debug("Calling the guard model")
        model = self._model.for_role(AgentRole.GUARD, turn.model)
        screening: ScreeningDto | None = await invoke_structured(model, ScreeningDto, messages)
        return screening.to_domain() if screening else None
