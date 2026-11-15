from typing import Protocol

from agent_runtime.domain.agent.peer_agent import PeerAgent


class ListAgentsPort(Protocol):
    async def handle(self) -> tuple[PeerAgent, ...]: ...
