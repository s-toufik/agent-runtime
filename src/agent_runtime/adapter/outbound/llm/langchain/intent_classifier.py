from langchain_core.messages import HumanMessage, SystemMessage
from pycraftcore.logger.port import Logger

from agent_runtime.adapter.outbound.llm.langchain.chat_models import ChatModels
from agent_runtime.adapter.outbound.llm.langchain.context_window import (
    ContextWindow,
    count_message_tokens,
    input_budget,
)
from agent_runtime.adapter.outbound.llm.langchain.dto import UnderstandingDto
from agent_runtime.adapter.outbound.llm.langchain.messages import render
from agent_runtime.adapter.outbound.llm.langchain.model_call import invoke_structured
from agent_runtime.adapter.outbound.llm.langchain.prompts.context import (
    context_request,
    context_system_prompt,
)
from agent_runtime.adapter.outbound.llm.langchain.token_counter import count_tokens
from agent_runtime.adapter.outbound.llm.model_catalog import AgentRole
from agent_runtime.domain.conversation.conversation import Conversation
from agent_runtime.domain.turn.turn import Turn
from agent_runtime.domain.turn.understanding import Understanding


class LangChainIntentClassifier:
    def __init__(self, models: ChatModels, window: ContextWindow, logger: Logger) -> None:
        self._models = models
        self._window = window
        self._logger = logger

    async def understand(self, conversation: Conversation, turn: Turn) -> Understanding | None:
        pending = conversation.pending
        schema: dict = UnderstandingDto.model_json_schema()
        system = SystemMessage(content=context_system_prompt(schema))
        budget: int = input_budget(
            turn.settings.context_tokens, turn.settings.output_tokens, [schema]
        )
        history = self._window.history(
            conversation, budget - count_message_tokens([system]) - count_tokens(turn.request)
        )
        messages = [
            system,
            HumanMessage(
                content=context_request(
                    render(history), pending.render() if pending else None, turn.request
                )
            ),
        ]
        self._logger.debug("Calling the context model")
        model = self._models.for_role(AgentRole.CONTEXT, turn.model)
        understood = await invoke_structured(model, UnderstandingDto, messages)
        return understood.to_domain() if understood else None
