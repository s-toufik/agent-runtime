from typing import Protocol

from agent_runtime.domain.conversation.conversation import Conversation
from agent_runtime.domain.turn.plan import Plan
from agent_runtime.domain.turn.screening import Screening
from agent_runtime.domain.turn.turn import Turn


class Guard(Protocol):
    async def screen(
        self, conversation: Conversation, turn: Turn, plan: Plan
    ) -> Screening | None: ...
