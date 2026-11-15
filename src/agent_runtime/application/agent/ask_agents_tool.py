import asyncio

from agent_runtime.application.agent.peer_directory import PeerDirectory
from agent_runtime.application.port.outbound.peer_agents import PeerAgentsPort
from agent_runtime.application.port.outbound.tool_provider import ToolPort
from agent_runtime.domain.agent.peer_agent import PeerAgent
from agent_runtime.domain.agent.peer_reply import PeerOutcome, PeerReply, PeerRequest
from agent_runtime.domain.tool.tool_call import ToolCall
from agent_runtime.domain.tool.tool_result import ToolResult
from agent_runtime.domain.tool.tool_specification import ToolSpecification

ASK_AGENTS: str = "ask_agents"
_DESCRIPTION: str = (
    "Ask other agents. Each request goes to one agent with a message that stands on its own "
    "(the agent does not see this conversation). Several requests in one call run at the same "
    "time: put independent parts of the task together. Every answer comes back, marked "
    "answered, needs_input, refused, failed or unreachable.\nAgents:\n{agents}"
)


class AskAgentsTool:
    def __init__(self, peers: tuple[PeerAgent, ...], client: PeerAgentsPort) -> None:
        self._peers = {peer.name: peer for peer in peers}
        self._client = client

    @property
    def specification(self) -> ToolSpecification:
        return ToolSpecification(
            name=ASK_AGENTS,
            description=_DESCRIPTION.format(
                agents="\n".join(f"- {peer.render()}" for peer in self._peers.values())
            ),
            parameters={
                "type": "object",
                "properties": {
                    "requests": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {
                                "agent": {"type": "string", "enum": sorted(self._peers)},
                                "message": {"type": "string", "minLength": 1},
                            },
                            "required": ["agent", "message"],
                        },
                    }
                },
                "required": ["requests"],
            },
        )

    async def invoke(self, call: ToolCall) -> ToolResult:
        requests: list[PeerRequest] | None = _requests(call.arguments)
        if not requests:
            return ToolResult.failure(
                call.id, ASK_AGENTS, "Give 'requests': a list of {agent, message}."
            )
        replies: list[PeerReply] = list(await asyncio.gather(*(self._ask(r) for r in requests)))
        return ToolResult(
            call_id=call.id,
            tool_name=ASK_AGENTS,
            output="\n\n".join(reply.render() for reply in replies),
        )

    async def _ask(self, request: PeerRequest) -> PeerReply:
        if request.agent not in self._peers:
            known = ", ".join(sorted(self._peers))
            return PeerReply(
                request.agent, PeerOutcome.UNREACHABLE, f"No agent named so. Known: {known}."
            )
        return await self._client.ask(request)


class AskAgentsProvider:
    def __init__(self, client: PeerAgentsPort, directory: PeerDirectory) -> None:
        self._client = client
        self._directory = directory

    async def tools(self) -> list[ToolPort]:
        found = await asyncio.gather(
            *(self._client.describe(name) for name in self._client.names),
            return_exceptions=True,
        )
        peers: tuple[PeerAgent, ...] = tuple(peer for peer in found if isinstance(peer, PeerAgent))
        self._directory.replace(peers)
        return [AskAgentsTool(peers, self._client)] if peers else []


def _requests(arguments: dict) -> list[PeerRequest] | None:
    raw = arguments.get("requests")
    if not isinstance(raw, list):
        return None
    requests: list[PeerRequest] = []
    for item in raw:
        if not isinstance(item, dict):
            return None
        agent, message = item.get("agent"), item.get("message")
        if not isinstance(agent, str) or not isinstance(message, str) or not message.strip():
            return None
        requests.append(PeerRequest(agent.strip(), message.strip()))
    return requests
