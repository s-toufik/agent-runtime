from agent_runtime.application.agent.peer_directory import PeerDirectory
from agent_runtime.domain.agent.agent import Agent
from agent_runtime.domain.agent.peer_agent import PeerAgent


class ListAgents:
    def __init__(self, agent: Agent, directory: PeerDirectory) -> None:
        self._agent = agent
        self._directory = directory

    async def handle(self) -> tuple[PeerAgent, ...]:
        itself = PeerAgent(self._agent.name, self._agent.description, self._agent.skills)
        return (itself, *self._directory.peers)
