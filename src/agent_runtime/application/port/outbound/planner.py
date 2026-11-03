from typing import Protocol

from agent_runtime.domain.conversation.conversation import Conversation
from agent_runtime.domain.tool.tool_specification import ToolSpecification
from agent_runtime.domain.turn.plan import Plan
from agent_runtime.domain.turn.turn import Turn


class Planner(Protocol):
    async def plan(
        self, conversation: Conversation, turn: Turn, tools: list[ToolSpecification]
    ) -> Plan | None: ...
