from collections.abc import AsyncIterator
from typing import cast

from agent_runtime.adapter.inbound.web.controller.stream_agent_controller import (
    StreamAgentController,
)
from agent_runtime.adapter.inbound.web.schema.agent_request_schema import AgentRequestSchema
from bootstrap.router.agent.stream_agent_router import StreamAgentRouter
from tests.support.web import EVERY_FRAMEWORK, build_app, http_client


class FakeController:
    def __init__(self) -> None:
        self.received: AgentRequestSchema | None = None

    async def execute(self, request: AgentRequestSchema) -> AsyncIterator[bytes]:
        self.received = request

        async def body() -> AsyncIterator[bytes]:
            yield b"event: final\ndata: {}\n\n"

        return body()


@EVERY_FRAMEWORK
async def test_posting_to_the_endpoint_forwards_the_parsed_request_to_the_controller(
    framework,
) -> None:
    controller = FakeController()
    routes = StreamAgentRouter(cast(StreamAgentController, controller)).routes

    async with http_client(build_app(framework, routes)) as client:
        response = await client.post(
            "/v1/stream",
            json={"message": "hi", "model_name": "qwen3-14b", "request_id": "r1"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert controller.received is not None
    assert controller.received.message == "hi"
    assert controller.received.model_name == "qwen3-14b"
    assert controller.received.request_id == "r1"
    assert response.text == "event: final\ndata: {}\n\n"


@EVERY_FRAMEWORK
async def test_an_invalid_body_is_rejected_before_the_controller(framework) -> None:
    controller = FakeController()
    routes = StreamAgentRouter(cast(StreamAgentController, controller)).routes

    async with http_client(build_app(framework, routes)) as client:
        response = await client.post("/v1/stream", json={"message": ""})

    assert 400 <= response.status_code < 500
    assert controller.received is None
