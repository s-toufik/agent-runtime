from typing import Protocol

from agent_runtime.domain.conversation.conversation import Conversation
from agent_runtime.domain.tool.tool_specification import ToolSpecification
from agent_runtime.domain.turn.draft import Draft
from agent_runtime.domain.turn.turn import Turn


class Actor(Protocol):
    async def act(
        self, conversation: Conversation, turn: Turn, tools: list[ToolSpecification]
    ) -> Draft: ...
