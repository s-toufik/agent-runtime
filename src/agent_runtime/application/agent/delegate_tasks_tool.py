import asyncio

from agent_runtime.application.agent.peer_directory import PeerDirectory
from agent_runtime.application.port.outbound.peer_agents import PeerAgentsPort
from agent_runtime.application.port.outbound.tool_provider import ToolPort
from agent_runtime.application.port.outbound.turn_event_publisher import TurnEventPublisher
from agent_runtime.domain.agent.peer_agent import PeerAgent
from agent_runtime.domain.agent.peer_reply import PeerOutcome, PeerReply, PeerRequest
from agent_runtime.domain.event.progress import Progress
from agent_runtime.domain.event.turn_event import TurnEvent
from agent_runtime.domain.tool.tool_call import ToolCall
from agent_runtime.domain.tool.tool_context import ToolContext
from agent_runtime.domain.tool.tool_result import ToolResult
from agent_runtime.domain.tool.tool_specification import ToolSpecification

DELEGATE_TASKS: str = "delegate_tasks"
_DESCRIPTION: str = (
    "Hand tasks to other agents. Each task goes to one agent and must stand on its own (the "
    "agent does not see this conversation). Tasks in one call run at the same time: put "
    "independent parts of the work together. Every result comes back, marked answered, "
    "needs_input, refused, failed or unreachable.\nAgents:\n{agents}"
)


class DelegateTasksTool:
    def __init__(
        self,
        peers: tuple[PeerAgent, ...],
        client: PeerAgentsPort,
        events: TurnEventPublisher | None = None,
    ) -> None:
        self._peers = {peer.name: peer for peer in peers}
        self._client = client
        self._events = events

    @property
    def specification(self) -> ToolSpecification:
        return ToolSpecification(
            name=DELEGATE_TASKS,
            description=_DESCRIPTION.format(
                agents="\n".join(f"- {peer.render()}" for peer in self._peers.values())
            ),
            parameters={
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {
                                "agent": {"type": "string", "enum": sorted(self._peers)},
                                "task": {"type": "string", "minLength": 1},
                            },
                            "required": ["agent", "task"],
                        },
                    }
                },
                "required": ["tasks"],
            },
        )

    async def invoke(self, call: ToolCall, context: ToolContext) -> ToolResult:
        requests: list[PeerRequest] | None = _requests(call.arguments, context)
        if not requests:
            return ToolResult.failure(
                call.id, DELEGATE_TASKS, "Give 'tasks': a list of {agent, task}."
            )
        replies: list[PeerReply] = list(
            await asyncio.gather(*(self._delegate(r) for r in requests))
        )
        return ToolResult(
            call_id=call.id,
            tool_name=DELEGATE_TASKS,
            output="\n\n".join(reply.render() for reply in replies),
        )

    async def _delegate(self, request: PeerRequest) -> PeerReply:
        await self._tell(Progress.agent_started(request.agent, request.message))
        reply: PeerReply = await self._ask(request)
        await self._tell(Progress.agent_finished(reply))
        return reply

    async def _ask(self, request: PeerRequest) -> PeerReply:
        if request.agent not in self._peers:
            known = ", ".join(sorted(self._peers))
            return PeerReply(
                request.agent, PeerOutcome.UNREACHABLE, f"No agent named so. Known: {known}."
            )

        async def forward(progress: Progress) -> None:
            await self._tell(progress.under(request.agent))

        return await self._client.ask(request, forward)

    async def _tell(self, progress: Progress) -> None:
        if self._events is not None:
            await self._events.publish(TurnEvent.progressed(progress))


class DelegateTasksProvider:
    def __init__(
        self,
        client: PeerAgentsPort,
        directory: PeerDirectory,
        events: TurnEventPublisher | None = None,
    ) -> None:
        self._client = client
        self._directory = directory
        self._events = events

    async def tools(self) -> list[ToolPort]:
        found = await asyncio.gather(
            *(self._client.describe(name) for name in self._client.names),
            return_exceptions=True,
        )
        peers: tuple[PeerAgent, ...] = tuple(peer for peer in found if isinstance(peer, PeerAgent))
        self._directory.replace(peers)
        return [DelegateTasksTool(peers, self._client, self._events)] if peers else []


def _requests(arguments: dict, context: ToolContext) -> list[PeerRequest] | None:
    raw = arguments.get("tasks")
    if not isinstance(raw, list):
        return None
    requests: list[PeerRequest] = []
    for item in raw:
        if not isinstance(item, dict):
            return None
        agent, task = item.get("agent"), item.get("task")
        if not isinstance(agent, str) or not isinstance(task, str) or not task.strip():
            return None
        requests.append(
            PeerRequest(agent.strip(), task.strip(), context.conversation, context.model)
        )
    return requests
