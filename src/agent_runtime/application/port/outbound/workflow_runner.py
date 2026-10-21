from collections.abc import AsyncIterator
from typing import Protocol

from agent_runtime.domain.event.turn_event import TurnEvent
from agent_runtime.domain.turn.turn import Turn


class WorkflowRunner(Protocol):
    def run(self, conversation_id: str, turn: Turn) -> AsyncIterator[TurnEvent]: ...
