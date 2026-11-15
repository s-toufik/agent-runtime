import httpx
from pycraftcore.application_configuration.enum import ConnectorType
from pycraftcore.application_configuration.model.connector import A2aConnector
from pycraftcore.authentication.model.no_auth import NoAuth

from agent_runtime.adapter.inbound.a2a.a2a_agent_executor import A2aAgentExecutor
from agent_runtime.adapter.outbound.agent.a2a.a2a_peer_agents import A2aPeerAgents, peer_context
from agent_runtime.adapter.outbound.event.queue_turn_event_stream import QueueTurnEventStream
from agent_runtime.application.use_case.run_a2a_task import RunA2aTask
from agent_runtime.domain.agent.peer_reply import PeerOutcome, PeerRequest
from tests.bootstrap.application.fastapi.support import a2a_handler, fastapi_api
from tests.support.a2a import ANSWERED, PLANNED, Models, ScriptedUseCase

CONVERSATION = "0f6c2a8e-3b1d-4c55-9a77-2e4b8d1f6a90"
A2A_ID_SIZE = 36


def _peer_app(logger, handle_message):
    run_task = RunA2aTask(handle_message, QueueTurnEventStream, Models())
    executor = A2aAgentExecutor(lambda: run_task, logger)
    return fastapi_api(logger, lambda: None, Models, a2a=a2a_handler(executor))


def _connector(url: str = "http://chat") -> A2aConnector:
    return A2aConnector(
        name="agent_chat", type=ConnectorType.a2a, auth=NoAuth(), base_url=url, timeout=5
    )


def _peers(logger, app) -> A2aPeerAgents:
    def client(connector: A2aConnector) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=connector.base_url
        )

    return A2aPeerAgents({"chat": _connector()}, logger, http_client=client)


async def test_a_peer_is_described_from_its_card(logger) -> None:
    peers = _peers(logger, _peer_app(logger, ScriptedUseCase()))

    peer = await peers.describe("chat")

    assert peer.name == "chat"
    assert peer.description == "the homelab test assistant"
    assert [skill.id for skill in peer.skills] == ["answer"]
    await peers.close()


async def test_a_peer_answers_auto_approved_with_the_model_in_its_own_part_of_the_conversation(
    logger,
) -> None:
    handle_message = ScriptedUseCase(ANSWERED)
    peers = _peers(logger, _peer_app(logger, handle_message))

    reply = await peers.ask(PeerRequest("chat", "meaning?", CONVERSATION, "m"))

    assert (reply.outcome, reply.text) == (PeerOutcome.ANSWERED, "42")
    [request] = handle_message.requests
    assert request.message == "meaning?"
    assert request.auto_approve is True
    assert request.model_name == "m"
    assert request.request_id == peer_context(CONVERSATION, "chat")
    await peers.close()


def test_each_peer_has_its_own_part_of_the_conversation_within_the_a2a_id_size() -> None:
    chat, observation = (
        peer_context(CONVERSATION, "chat"),
        peer_context(CONVERSATION, "observation"),
    )

    assert chat == peer_context(CONVERSATION, "chat")
    assert chat != observation
    assert len(chat) == len(observation) == A2A_ID_SIZE


async def test_a_peer_that_waits_for_input_says_what_it_waits_for(logger) -> None:
    peers = _peers(logger, _peer_app(logger, ScriptedUseCase(PLANNED)))

    reply = await peers.ask(PeerRequest("chat", "do it", CONVERSATION, "m"))

    assert reply.outcome is PeerOutcome.NEEDS_INPUT
    assert "### Plan" in reply.text
    await peers.close()


async def test_a_peer_that_cannot_be_reached_is_reported_not_raised(logger) -> None:
    def refused(connector: A2aConnector) -> httpx.AsyncClient:
        def fail(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused", request=request)

        return httpx.AsyncClient(transport=httpx.MockTransport(fail))

    peers = A2aPeerAgents({"chat": _connector()}, logger, http_client=refused)

    reply = await peers.ask(PeerRequest("chat", "hello", CONVERSATION, "m"))

    assert reply.outcome is PeerOutcome.UNREACHABLE
    assert logger.messages("warning")
    await peers.close()


def test_an_agent_without_a_url_is_not_offered(logger) -> None:
    peers = A2aPeerAgents({"chat": _connector(""), "travel": _connector("http://travel")}, logger)

    assert peers.names == ("travel",)
