from collections.abc import Awaitable, Callable
from typing import Protocol

from agent_runtime.domain.agent.peer_agent import PeerAgent
from agent_runtime.domain.agent.peer_reply import PeerReply, PeerRequest
from agent_runtime.domain.event.progress import Progress

ProgressListener = Callable[[Progress], Awaitable[None]]


class PeerAgentsPort(Protocol):
    @property
    def names(self) -> tuple[str, ...]: ...

    async def describe(self, name: str) -> PeerAgent: ...

    async def ask(
        self, request: PeerRequest, progress: ProgressListener | None = None
    ) -> PeerReply: ...
