from typing import Protocol

from agent_runtime.domain.conversation.message import Message
from agent_runtime.domain.turn.turn import Turn


class Summarizer(Protocol):
    async def summarize(self, turn: Turn, summary: str, messages: list[Message]) -> str: ...
