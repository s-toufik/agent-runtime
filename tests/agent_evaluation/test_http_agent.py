import json

import httpx
import pytest

from agent_evaluation.adapter.agent.http_agent import HttpAgent
from agent_evaluation.domain.exception import AgentUnavailable


def _sse(*events: tuple[str, dict]) -> bytes:
    return "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events).encode()


FINAL = {
    "session_id": "c1",
    "content": "Done: eval.csv",
    "metadata": {
        "outcome": "answered",
        "tools": "python_executor, file_writer",
        "model": "m",
        "input_tokens": "1200",
        "output_tokens": "80",
        "iteration": "3",
    },
}


def _agent(handler, models_endpoint: str | None = "/v1/models") -> HttpAgent:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return HttpAgent(client, "http://agent:8001/", "/v1/stream", models_endpoint, "m", 30, {})


async def test_a_streamed_turn_becomes_a_reply() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        body = _sse(
            ("status", {"type": "status", "content": "Formulating a plan"}),
            ("token", {"type": "token", "content": "Do"}),
            ("final", FINAL),
            ("complete", {"type": "complete", "content": ""}),
        )
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    reply = await _agent(handler).send("hi", "conv-1", True)

    assert requests == [
        {"message": "hi", "model_name": "m", "request_id": "conv-1", "auto_approve": True}
    ]
    assert reply.content == "Done: eval.csv" and reply.outcome == "answered"
    assert reply.tools == ("python_executor", "file_writer")
    assert reply.statuses == ("Formulating a plan",)
    assert (reply.input_tokens, reply.output_tokens, reply.iterations) == (1200, 80, 3)


async def test_a_stream_without_an_answer_means_the_agent_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = _sse(("error", {"type": "error", "content": "The assistant is unavailable"}))
        return httpx.Response(200, content=body)

    with pytest.raises(AgentUnavailable, match="The assistant is unavailable"):
        await _agent(handler).send("hi", "conv-1", False)


async def test_a_refused_connection_or_an_http_error_means_unavailable() -> None:
    def busy(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Server is at capacity")

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(AgentUnavailable, match="HTTP 503"):
        await _agent(busy).send("hi", "c", False)
    with pytest.raises(AgentUnavailable, match="ConnectError"):
        await _agent(down).send("hi", "c", False)


async def test_preflight_checks_the_model_is_served() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"models": [{"name": "other"}]})

    with pytest.raises(AgentUnavailable, match="pick one of: other"):
        await _agent(handler).preflight()


async def test_preflight_can_be_switched_off() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    await _agent(handler, models_endpoint=None).preflight()
