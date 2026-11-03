from typing import Protocol

from agent_evaluation.domain.reply import AgentReply


class Agent(Protocol):
    async def preflight(self) -> None: ...

    async def send(self, message: str, conversation_id: str, auto_approve: bool) -> AgentReply: ...
