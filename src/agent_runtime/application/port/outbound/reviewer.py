from typing import Protocol

from agent_runtime.domain.conversation.conversation import Conversation
from agent_runtime.domain.turn.turn import Turn
from agent_runtime.domain.turn.verdict import Verdict


class Reviewer(Protocol):
    async def review(self, conversation: Conversation, turn: Turn) -> Verdict | None: ...
