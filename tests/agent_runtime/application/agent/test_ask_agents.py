import asyncio

from agent_runtime.application.agent.ask_agents_tool import (
    ASK_AGENTS,
    AskAgentsProvider,
    AskAgentsTool,
)
from agent_runtime.application.agent.peer_directory import PeerDirectory
from agent_runtime.application.use_case.list_agents import ListAgents
from agent_runtime.domain.agent.agent import Agent
from agent_runtime.domain.agent.agent_skill import AgentSkill
from agent_runtime.domain.agent.peer_agent import PeerAgent
from agent_runtime.domain.agent.peer_reply import PeerOutcome, PeerReply, PeerRequest
from agent_runtime.domain.tool.tool_call import ToolCall

CHAT = PeerAgent("chat", "the conversation agent", (AgentSkill("answer", "Answer", "Explains."),))
OBSERVATION = PeerAgent("observation", "the observation agent")


class FakePeers:
    def __init__(self, *peers: PeerAgent, down: tuple[str, ...] = ()) -> None:
        self._peers = {peer.name: peer for peer in peers}
        self._down = down
        self.asked: list[PeerRequest] = []
        self.running = 0
        self.most_at_once = 0

    @property
    def names(self) -> tuple[str, ...]:
        return (*self._peers, *self._down)

    async def describe(self, name: str) -> PeerAgent:
        if name in self._down:
            raise ConnectionError(f"{name} is down")
        return self._peers[name]

    async def ask(self, request: PeerRequest) -> PeerReply:
        self.asked.append(request)
        self.running += 1
        self.most_at_once = max(self.most_at_once, self.running)
        await asyncio.sleep(0.01)
        self.running -= 1
        return PeerReply(request.agent, PeerOutcome.ANSWERED, f"{request.agent} says hi")


def call(*requests: dict) -> ToolCall:
    return ToolCall("c1", ASK_AGENTS, {"requests": list(requests)})


async def test_the_requests_of_one_call_run_at_the_same_time_and_all_come_back() -> None:
    peers = FakePeers(CHAT, OBSERVATION)
    tool = AskAgentsTool((CHAT, OBSERVATION), peers)

    result = await tool.invoke(
        call({"agent": "chat", "message": "explain"}, {"agent": "observation", "message": "pods?"})
    )

    assert peers.most_at_once == 2
    assert result.error is None
    assert "## chat (answered)\nchat says hi" in result.output
    assert "## observation (answered)\nobservation says hi" in result.output


def test_the_tool_lists_the_agents_and_their_skills_and_accepts_only_them() -> None:
    specification = AskAgentsTool((CHAT, OBSERVATION), FakePeers()).specification

    assert specification.name == "ask_agents"
    assert "- chat: the conversation agent (Answer: Explains.)" in specification.description
    agents = specification.parameters["properties"]["requests"]["items"]["properties"]["agent"]
    assert agents["enum"] == ["chat", "observation"]


async def test_an_unknown_agent_is_answered_without_calling_anyone() -> None:
    peers = FakePeers(CHAT)
    tool = AskAgentsTool((CHAT,), peers)

    result = await tool.invoke(call({"agent": "travel", "message": "Lisbon?"}))

    assert peers.asked == []
    assert "## travel (unreachable)\nNo agent named so. Known: chat." in result.output


async def test_malformed_requests_are_a_tool_error() -> None:
    tool = AskAgentsTool((CHAT,), FakePeers(CHAT))

    for arguments in ({}, {"requests": "chat"}, {"requests": [{"agent": "chat"}]}):
        result = await tool.invoke(ToolCall("c1", ASK_AGENTS, arguments))
        assert result.error and "requests" in result.error


async def test_the_provider_offers_the_reachable_agents_and_records_them() -> None:
    directory = PeerDirectory()
    provider = AskAgentsProvider(FakePeers(CHAT, down=("observation",)), directory)

    [tool] = await provider.tools()

    assert "observation" not in tool.specification.description
    assert directory.peers == (CHAT,)


async def test_without_a_reachable_agent_there_is_no_tool() -> None:
    directory = PeerDirectory()

    assert await AskAgentsProvider(FakePeers(down=("chat",)), directory).tools() == []
    assert directory.peers == ()


async def test_the_list_of_agents_starts_with_the_agent_itself() -> None:
    directory = PeerDirectory()
    directory.replace([CHAT])
    orchestration = Agent("orchestration", "the orchestrator", peers=("chat",))

    agents = await ListAgents(orchestration, directory).handle()

    assert [agent.name for agent in agents] == ["orchestration", "chat"]
