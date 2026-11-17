import asyncio
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

import httpx
from a2a.client import A2ACardResolver, Client, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types.a2a_pb2 import (
    AgentCard,
    CancelTaskRequest,
    Role,
    SendMessageRequest,
    StreamResponse,
    Task,
    TaskState,
)
from google.protobuf import json_format
from pycraftcore.application_configuration.model.connector import A2aConnector
from pycraftcore.logger.port import Logger

from agent_runtime.application.port.outbound.peer_agents import ProgressListener
from agent_runtime.domain.a2a.turn_options import AUTO_APPROVE_KEY, MODEL_KEY
from agent_runtime.domain.agent.agent_skill import AgentSkill
from agent_runtime.domain.agent.peer_agent import PeerAgent
from agent_runtime.domain.agent.peer_reply import PeerOutcome, PeerReply, PeerRequest
from agent_runtime.domain.event.progress import PROGRESS_KEY, Progress

OUTCOMES: dict[int, PeerOutcome] = {
    TaskState.TASK_STATE_COMPLETED: PeerOutcome.ANSWERED,
    TaskState.TASK_STATE_INPUT_REQUIRED: PeerOutcome.NEEDS_INPUT,
    TaskState.TASK_STATE_REJECTED: PeerOutcome.REFUSED,
    TaskState.TASK_STATE_FAILED: PeerOutcome.FAILED,
    TaskState.TASK_STATE_CANCELED: PeerOutcome.FAILED,
}

CANCEL_TIMEOUT_SECONDS: float = 5.0

PEER_CONTEXTS: uuid.UUID = uuid.uuid5(uuid.NAMESPACE_URL, "urn:agent-runtime:peer-context")


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

    async def ask(
        self, request: PeerRequest, progress: ProgressListener | None = None
    ) -> PeerReply:
        try:
            run: _PeerRun = await self._send(request, progress)
        except Exception as exception:
            self._logger.warning(f"Agent '{request.agent}' did not answer: {exception}")
            return PeerReply(request.agent, PeerOutcome.UNREACHABLE, str(exception))
        if run.state is None:
            return PeerReply(request.agent, PeerOutcome.FAILED, "The agent sent no task back.")
        outcome: PeerOutcome = OUTCOMES.get(run.state, PeerOutcome.FAILED)
        return PeerReply(request.agent, outcome, run.text(outcome))

    async def close(self) -> None:
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()

    async def _send(self, request: PeerRequest, progress: ProgressListener | None) -> _PeerRun:
        card: AgentCard = self._cards.get(request.agent) or await self._card(request.agent)
        config = ClientConfig(httpx_client=self._client(request.agent), streaming=True)
        client = await create_client(card, client_config=config)
        message = new_text_message(request.message, role=Role.ROLE_USER)
        message.context_id = peer_context(request.conversation, request.agent)
        message.metadata.update({AUTO_APPROVE_KEY: True, MODEL_KEY: request.model})
        run = _PeerRun()
        try:
            async for response in client.send_message(SendMessageRequest(message=message)):
                update: Progress | None = run.read(response)
                if update is not None and progress is not None:
                    await progress(update)
        except asyncio.CancelledError:
            if run.task_id:
                await self._cancel(client, request.agent, run.task_id)
            raise
        return run

    async def _cancel(self, client: Client, agent: str, task_id: str) -> None:
        try:
            async with asyncio.timeout(CANCEL_TIMEOUT_SECONDS):
                await client.cancel_task(CancelTaskRequest(id=task_id))
        except Exception as exception:
            self._logger.warning(f"Agent '{agent}' kept task {task_id}: {exception}")
        else:
            self._logger.info(f"Agent '{agent}' cancelled task {task_id}")

    async def _card(self, name: str) -> AgentCard:
        await self.describe(name)
        return self._cards[name]

    def _client(self, name: str) -> httpx.AsyncClient:
        if name not in self._clients:
            self._clients[name] = self._http_client(self._connectors[name])
        return self._clients[name]


def peer_context(conversation: str, agent: str) -> str:
    return str(uuid.uuid5(PEER_CONTEXTS, f"{conversation}:{agent}"))


def _http_client(connector: A2aConnector) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=float(connector.timeout))


@dataclass
class _PeerRun:
    """What a peer has said so far: its task, last state, answer and last status text."""

    task_id: str = ""
    state: int | None = None
    answer: list[str] = field(default_factory=list)
    status: list[str] = field(default_factory=list)

    def read(self, response: StreamResponse) -> Progress | None:
        if response.HasField("task"):
            self._take_task(response.task)
        elif response.HasField("artifact_update"):
            update = response.artifact_update
            self.task_id = self.task_id or update.task_id
            if not update.append:
                self.answer.clear()
            self.answer.extend(part.text for part in update.artifact.parts)
        elif response.HasField("status_update"):
            update = response.status_update
            self.task_id = self.task_id or update.task_id
            self.state = update.status.state
            if update.status.HasField("message"):
                self.status = [part.text for part in update.status.message.parts]
            return _progress(update.metadata)
        return None

    def text(self, outcome: PeerOutcome) -> str:
        if outcome is PeerOutcome.ANSWERED and self.answer:
            return "\n".join(self.answer)
        return "\n".join(self.status)

    def _take_task(self, task: Task) -> None:
        self.task_id = task.id
        self.state = task.status.state
        if task.artifacts:
            self.answer = [part.text for artifact in task.artifacts for part in artifact.parts]
        if task.status.HasField("message"):
            self.status = [part.text for part in task.status.message.parts]


def _progress(metadata) -> Progress | None:
    fields = json_format.MessageToDict(metadata) if metadata else {}
    raw = fields.get(PROGRESS_KEY)
    if isinstance(raw, str):
        return Progress.from_json(raw)
    return Progress.from_dict(raw) if isinstance(raw, dict) else None
