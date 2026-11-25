import asyncio

from agent_runtime.application.agent.delegate_tasks_tool import (
    DELEGATE_TASKS,
    DelegateTasksProvider,
    DelegateTasksTool,
)
from agent_runtime.application.agent.peer_directory import PeerDirectory
from agent_runtime.application.use_case.list_agents import ListAgents
from agent_runtime.domain.agent.agent import Agent
from agent_runtime.domain.agent.agent_skill import AgentSkill
from agent_runtime.domain.agent.peer_agent import PeerAgent
from agent_runtime.domain.agent.peer_reply import PeerOutcome, PeerReply, PeerRequest
from agent_runtime.domain.event.progress import Progress, ProgressKind
from agent_runtime.domain.event.turn_event import TurnEvent
from agent_runtime.domain.tool.tool_call import ToolCall
from agent_runtime.domain.tool.tool_context import ToolContext

CHAT = PeerAgent("chat", "the conversation agent", (AgentSkill("answer", "Answer", "Explains."),))
OBSERVATION = PeerAgent("observation", "the observation agent")
CONTEXT = ToolContext(conversation="conversation-7", model="nemotron")


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

    async def ask(self, request: PeerRequest, progress=None) -> PeerReply:
        self.asked.append(request)
        self.running += 1
        self.most_at_once = max(self.most_at_once, self.running)
        if progress is not None:
            await progress(Progress(ProgressKind.TOOL, call_id="t1", name="loki", state="running"))
        await asyncio.sleep(0.01)
        self.running -= 1
        return PeerReply(request.agent, PeerOutcome.ANSWERED, f"{request.agent} says hi")


def call(*requests: dict) -> ToolCall:
    return ToolCall("c1", DELEGATE_TASKS, {"tasks": list(requests)})


async def test_the_requests_of_one_call_run_at_the_same_time_and_all_come_back() -> None:
    peers = FakePeers(CHAT, OBSERVATION)
    tool = DelegateTasksTool((CHAT, OBSERVATION), peers)

    result = await tool.invoke(
        call({"agent": "chat", "task": "explain"}, {"agent": "observation", "task": "pods?"}),
        CONTEXT,
    )

    assert peers.most_at_once == 2
    assert result.error is None
    assert "## chat (answered)\nchat says hi" in result.output
    assert "## observation (answered)\nobservation says hi" in result.output


async def test_every_agent_works_in_the_turn_s_model_and_conversation() -> None:
    peers = FakePeers(CHAT, OBSERVATION)
    tool = DelegateTasksTool((CHAT, OBSERVATION), peers)

    await tool.invoke(
        call({"agent": "chat", "task": "explain"}, {"agent": "observation", "task": "pods?"}),
        CONTEXT,
    )

    assert {(r.agent, r.conversation, r.model) for r in peers.asked} == {
        ("chat", "conversation-7", "nemotron"),
        ("observation", "conversation-7", "nemotron"),
    }


def test_the_tool_accepts_only_the_agents_it_found_and_leaves_their_roster_to_the_prompts() -> None:
    specification = DelegateTasksTool((CHAT, OBSERVATION), FakePeers()).specification

    assert specification.name == "delegate_tasks"
    assert specification.description.startswith("Hand tasks to other agents.")
    assert "the conversation agent" not in specification.description
    agents = specification.parameters["properties"]["tasks"]["items"]["properties"]["agent"]
    assert agents["enum"] == ["chat", "observation"]


async def test_an_unknown_agent_is_answered_without_calling_anyone() -> None:
    peers = FakePeers(CHAT)
    tool = DelegateTasksTool((CHAT,), peers)

    result = await tool.invoke(call({"agent": "travel", "task": "Lisbon?"}), CONTEXT)

    assert peers.asked == []
    assert "## travel (unreachable)\nNo agent named so. Known: chat." in result.output


async def test_malformed_requests_are_a_tool_error() -> None:
    tool = DelegateTasksTool((CHAT,), FakePeers(CHAT))

    for arguments in ({}, {"tasks": "chat"}, {"tasks": [{"agent": "chat"}]}):
        result = await tool.invoke(ToolCall("c1", DELEGATE_TASKS, arguments), CONTEXT)
        assert result.error and "tasks" in result.error


async def test_the_provider_offers_the_reachable_agents_and_records_them() -> None:
    directory = PeerDirectory()
    provider = DelegateTasksProvider(FakePeers(CHAT, down=("observation",)), directory)

    [tool] = await provider.tools()

    assert "observation" not in tool.specification.description
    assert directory.peers == (CHAT,)


async def test_without_a_reachable_agent_there_is_no_tool() -> None:
    directory = PeerDirectory()

    assert await DelegateTasksProvider(FakePeers(down=("chat",)), directory).tools() == []
    assert directory.peers == ()


async def test_the_list_of_agents_starts_with_the_agent_itself() -> None:
    directory = PeerDirectory()
    directory.replace([CHAT])
    orchestration = Agent("orchestration", "the orchestrator", peers=("chat",))

    agents = await ListAgents(orchestration, directory).handle()

    assert [agent.name for agent in agents] == ["orchestration", "chat"]


class Events:
    def __init__(self) -> None:
        self.progress: list[Progress] = []

    async def publish(self, event: TurnEvent) -> None:
        assert event.progress is not None
        self.progress.append(event.progress)


async def test_each_task_reports_its_agent_starting_working_and_answering() -> None:
    events = Events()
    tool = DelegateTasksTool((CHAT, OBSERVATION), FakePeers(CHAT, OBSERVATION), events)

    await tool.invoke(
        call({"agent": "chat", "task": "explain"}, {"agent": "observation", "task": "pods?"}),
        CONTEXT,
    )

    seen = [(p.kind.value, p.path, p.name, p.state, p.detail) for p in events.progress]
    for agent, task in (("chat", "explain"), ("observation", "pods?")):
        started = ("agent", (), agent, "working", task)
        inside = ("tool", (agent,), "loki", "running", "")
        answered = ("agent", (), agent, "answered", "")
        assert seen.index(started) < seen.index(inside) < seen.index(answered)
    starts = [i for i, s in enumerate(seen) if s[0] == "agent" and s[3] == "working"]
    ends = [i for i, s in enumerate(seen) if s[0] == "agent" and s[3] == "answered"]
    assert max(starts) < min(ends)


class CountingMeter:
    def __init__(self) -> None:
        self.active: dict[str, int] = {}
        self.most: dict[str, int] = {}

    def started(self, agent: str) -> None:
        self.active[agent] = self.active.get(agent, 0) + 1
        self.most[agent] = max(self.most.get(agent, 0), self.active[agent])

    def ended(self, agent: str) -> None:
        self.active[agent] -= 1


async def test_each_delegation_is_counted_while_its_agent_works() -> None:
    meter = CountingMeter()
    tool = DelegateTasksTool((CHAT, OBSERVATION), FakePeers(CHAT, OBSERVATION), meter=meter)

    await tool.invoke(
        call({"agent": "chat", "task": "explain"}, {"agent": "observation", "task": "pods?"}),
        CONTEXT,
    )

    assert meter.most == {"chat": 1, "observation": 1}
    assert meter.active == {"chat": 0, "observation": 0}
