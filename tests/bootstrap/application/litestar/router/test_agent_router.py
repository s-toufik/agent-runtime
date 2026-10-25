from collections.abc import AsyncIterator
from typing import cast

from agent_runtime.adapter.inbound.web.exception.server_at_capacity_exception import (
    ServerAtCapacityException,
)
from agent_runtime.adapter.inbound.web.stream.stream_agent_controller import (
    StreamAgentController,
)
from agent_runtime.domain.llm_model.model_listing import ModelListing
from agent_runtime.domain.request.agent_request import AgentRequest
from tests.agent_runtime.application.fakes import LISTING
from tests.bootstrap.application.litestar.support import litestar_api
from tests.support.web import http_client

BODY = {"message": "hi", "model_name": "qwen3-14b", "request_id": "r1"}


class FakeAgent:
    def __init__(self, at_capacity: bool = False) -> None:
        self.received: AgentRequest | None = None
        self._at_capacity = at_capacity

    async def execute(self, request: AgentRequest) -> AsyncIterator[bytes]:
        if self._at_capacity:
            raise ServerAtCapacityException("Server is at capacity, please retry.")
        self.received = request

        async def frames() -> AsyncIterator[bytes]:
            yield b"event: final\ndata: {}\n\n"

        return frames()


class FakeModels:
    async def handle(self) -> ModelListing:
        return LISTING


def app_with(logger, agent: FakeAgent):
    return litestar_api(logger, lambda: cast(StreamAgentController, agent), FakeModels)


async def test_a_message_is_handed_to_the_agent_and_its_frames_are_streamed(logger) -> None:
    agent = FakeAgent()

    async with http_client(app_with(logger, agent)) as client:
        response = await client.post("/v1/stream", json=BODY)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.text == "event: final\ndata: {}\n\n"
    assert agent.received == AgentRequest(message="hi", model_name="qwen3-14b", request_id="r1")


async def test_an_invalid_message_is_rejected_before_the_agent(logger) -> None:
    agent = FakeAgent()

    async with http_client(app_with(logger, agent)) as client:
        response = await client.post("/v1/stream", json={"message": ""})

    assert response.status_code == 400
    assert agent.received is None


async def test_a_full_server_answers_503_with_a_detail(logger) -> None:
    async with http_client(app_with(logger, FakeAgent(at_capacity=True))) as client:
        response = await client.post("/v1/stream", json=BODY)

    assert response.status_code == 503
    assert response.json() == {"detail": "Server is at capacity, please retry."}


async def test_the_models_are_listed_with_their_pinned_steps(logger) -> None:
    async with http_client(app_with(logger, FakeAgent())) as client:
        response = await client.get("/v1/models")

    assert response.status_code == 200
    assert response.json() == {
        "models": [
            {"name": "m", "context_tokens": 8_000, "max_output_tokens": 1_000, "thinking": False}
        ],
        "pinned_steps": {"understand": "small"},
    }
