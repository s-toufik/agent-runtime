from typing import Protocol

from agent_orchestrator.domain.conversation.conversation import Conversation
from agent_orchestrator.domain.turn.plan import Plan
from agent_orchestrator.domain.turn.screening import Screening
from agent_orchestrator.domain.turn.turn import Turn


class Guard(Protocol):
    async def screen(
        self, conversation: Conversation, turn: Turn, plan: Plan
    ) -> Screening | None: ...
