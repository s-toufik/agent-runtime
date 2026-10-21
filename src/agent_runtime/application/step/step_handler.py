from typing import Protocol

from agent_runtime.domain.conversation.conversation import Conversation
from agent_runtime.domain.turn.turn import Turn
from agent_runtime.domain.workflow.step import Step


class StepHandler(Protocol):
    @property
    def step(self) -> Step: ...

    async def run(self, conversation: Conversation, turn: Turn) -> None: ...
