from collections.abc import Callable, Mapping

import httpx
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types.a2a_pb2 import AgentCard, Role, SendMessageRequest, Task, TaskState
from pycraftcore.application_configuration.model.connector import A2aConnector
from pycraftcore.context.request_id_context import request_id_context
from pycraftcore.logger.port import Logger

from agent_runtime.domain.a2a.turn_options import AUTO_APPROVE_KEY
from agent_runtime.domain.agent.agent_skill import AgentSkill
from agent_runtime.domain.agent.peer_agent import PeerAgent
from agent_runtime.domain.agent.peer_reply import PeerOutcome, PeerReply, PeerRequest

OUTCOMES: dict[int, PeerOutcome] = {
    TaskState.TASK_STATE_COMPLETED: PeerOutcome.ANSWERED,
    TaskState.TASK_STATE_INPUT_REQUIRED: PeerOutcome.NEEDS_INPUT,
    TaskState.TASK_STATE_REJECTED: PeerOutcome.REFUSED,
    TaskState.TASK_STATE_FAILED: PeerOutcome.FAILED,
    TaskState.TASK_STATE_CANCELED: PeerOutcome.FAILED,
}


class A2aPeerAgents:
    def __init__(
        self,
        connectors: Mapping[str, A2aConnector],
        logger: Logger,
        http_client: Callable[[A2aConnector], httpx.AsyncClient] | None = None,
    ) -> None:
        self._connectors = {name: c for name, c in connectors.items() if c.base_url.strip()}
        self._logger = logger
        self._http_client = http_client or _http_client
        self._clients: dict[str, httpx.AsyncClient] = {}
        self._cards: dict[str, AgentCard] = {}

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._connectors)

    async def describe(self, name: str) -> PeerAgent:
        connector: A2aConnector = self._connectors[name]
        resolver = A2ACardResolver(self._client(name), connector.base_url.rstrip("/"))
        card: AgentCard = await resolver.get_agent_card()
        self._cards[name] = card
        if card.name != name:
            self._logger.warning(f"Agent '{name}' calls itself '{card.name}' in its card")
        return PeerAgent(
            name=name,
            description=card.description,
            skills=tuple(
                AgentSkill(s.id, s.name, s.description, tuple(s.tags), tuple(s.examples))
                for s in card.skills
            ),
        )

    async def ask(self, request: PeerRequest) -> PeerReply:
        try:
            task: Task | None = await self._send(request)
        except Exception as exception:
            self._logger.warning(f"Agent '{request.agent}' did not answer: {exception}")
            return PeerReply(request.agent, PeerOutcome.UNREACHABLE, str(exception))
        if task is None:
            return PeerReply(request.agent, PeerOutcome.FAILED, "The agent sent no task back.")
        outcome: PeerOutcome = OUTCOMES.get(task.status.state, PeerOutcome.FAILED)
        return PeerReply(request.agent, outcome, _text(task, outcome))

    async def close(self) -> None:
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()

    async def _send(self, request: PeerRequest) -> Task | None:
        card: AgentCard = self._cards.get(request.agent) or await self._card(request.agent)
        config = ClientConfig(httpx_client=self._client(request.agent), streaming=False)
        client = await create_client(card, client_config=config)
        message = new_text_message(request.message, role=Role.ROLE_USER)
        conversation: str | None = request_id_context.get(None)
        if conversation:
            message.context_id = f"{conversation}:{request.agent}"
        message.metadata.update({AUTO_APPROVE_KEY: True})
        task: Task | None = None
        async for response in client.send_message(SendMessageRequest(message=message)):
            if response.HasField("task"):
                task = response.task
        return task

    async def _card(self, name: str) -> AgentCard:
        await self.describe(name)
        return self._cards[name]

    def _client(self, name: str) -> httpx.AsyncClient:
        if name not in self._clients:
            self._clients[name] = self._http_client(self._connectors[name])
        return self._clients[name]


def _http_client(connector: A2aConnector) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=float(connector.timeout))


def _text(task: Task, outcome: PeerOutcome) -> str:
    if outcome is PeerOutcome.ANSWERED and task.artifacts:
        return "\n".join(part.text for artifact in task.artifacts for part in artifact.parts)
    return "\n".join(part.text for part in task.status.message.parts)
