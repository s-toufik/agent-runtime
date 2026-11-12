from collections.abc import AsyncIterator
from typing import cast

from opentelemetry import trace

from agent_runtime.adapter.inbound.web.stream.stream_agent_controller import (
    StreamAgentController,
)
from agent_runtime.domain.request.agent_request import AgentRequest
from tests.agent_runtime.application.fakes import LISTING
from tests.bootstrap.application.litestar.support import litestar_api
from tests.support.tracing import by_name, is_child_of
from tests.support.web import http_client

BODY = {"message": "hi", "model_name": "qwen3-14b", "request_id": "r1"}
CALLER_TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"
CALLER_SPAN = "00f067aa0ba902b7"


class TracingAgent:
    async def execute(self, request: AgentRequest) -> AsyncIterator[bytes]:
        async def frames() -> AsyncIterator[bytes]:
            with trace.get_tracer("test").start_as_current_span("agent work"):
                yield b"event: final\ndata: {}\n\n"

        return frames()


class FakeModels:
    async def handle(self):
        return LISTING


def app(logger):
    return litestar_api(logger, lambda: cast(StreamAgentController, TracingAgent()), FakeModels)


async def test_a_message_is_one_trace_with_the_agent_s_work_inside_it(logger, spans) -> None:
    async with http_client(app(logger)) as client:
        await client.post("/v1/stream", json=BODY)

    recorded = by_name(spans)
    [server] = [span for name, span in recorded.items() if name.startswith("POST")]
    assert server.kind is trace.SpanKind.SERVER
    assert is_child_of(recorded["agent work"], server)


async def test_a_caller_s_traceparent_makes_the_request_part_of_its_trace(logger, spans) -> None:
    headers = {"traceparent": f"00-{CALLER_TRACE}-{CALLER_SPAN}-01"}

    async with http_client(app(logger)) as client:
        await client.post("/v1/stream", json=BODY, headers=headers)

    [server] = [span for span in spans.get_finished_spans() if span.name.startswith("POST")]
    assert server.context is not None
    assert f"{server.context.trace_id:032x}" == CALLER_TRACE
    assert server.parent is not None
    assert f"{server.parent.span_id:016x}" == CALLER_SPAN


async def test_health_checks_are_not_traced(logger, spans) -> None:
    async with http_client(app(logger)) as client:
        await client.get("/actuator/health")

    assert spans.get_finished_spans() == ()
