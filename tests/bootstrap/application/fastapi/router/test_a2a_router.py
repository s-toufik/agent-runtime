import asyncio
import json
from typing import Any

import httpx
from a2a.client import ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types.a2a_pb2 import Role, SendMessageRequest, TaskState

from agent_runtime.adapter.inbound.a2a.a2a_agent_executor import (
    AT_CAPACITY,
    TEXT_ONLY,
    A2aAgentExecutor,
)
from agent_runtime.adapter.inbound.a2a.a2a_task_presenter import APPROVAL_PROMPT
from agent_runtime.adapter.inbound.a2a.turn_options_extension import (
    AUTO_APPROVE_KEY,
    MODEL_KEY,
    TURN_OPTIONS_URI,
)
from agent_runtime.adapter.outbound.event.queue_turn_event_stream import QueueTurnEventStream
from agent_runtime.application.use_case.run_a2a_task import RunA2aTask
from tests.bootstrap.application.fastapi.support import a2a_handler, fastapi_api
from tests.support.a2a import ANSWERED, PLANNED, HangingUseCase, Models, ScriptedUseCase
from tests.support.web import http_client

VERSION = {"A2A-Version": "1.0"}


def _app(logger, handle_message, max_concurrent_turns: int = 200):
    run_task = RunA2aTask(handle_message, QueueTurnEventStream, Models())
    executor = A2aAgentExecutor(lambda: run_task, logger, max_concurrent_turns=max_concurrent_turns)
    handler = a2a_handler(executor)
    return fastapi_api(logger, lambda: None, Models, a2a=handler)


def _call(method: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": "a", "method": method, "params": params}


def _send(text: str, configuration: dict[str, Any] | None = None, **message: Any):
    params: dict[str, Any] = {
        "message": {"messageId": f"m-{text}", "role": "ROLE_USER", "parts": [{"text": text}]}
        | message
    }
    if configuration:
        params["configuration"] = configuration
    return _call("SendMessage", params)


async def _post(client: httpx.AsyncClient, body: dict[str, Any]) -> dict[str, Any]:
    response = await client.post("/a2a", json=body, headers=VERSION)
    assert response.status_code == 200
    return response.json()


async def _task(client: httpx.AsyncClient, body: dict[str, Any]) -> dict[str, Any]:
    reply = await _post(client, body)
    assert "error" not in reply, reply
    return reply["result"]["task"] if "task" in reply["result"] else reply["result"]


async def _polled(client: httpx.AsyncClient, task_id: str, state: str) -> dict[str, Any]:
    async def poll() -> dict[str, Any]:
        while (task := await _task(client, _call("GetTask", {"id": task_id})))["status"][
            "state"
        ] != state:
            await asyncio.sleep(0.01)
        return task

    return await asyncio.wait_for(poll(), timeout=5)


def _status_text(task: dict[str, Any]) -> str:
    return task["status"]["message"]["parts"][0]["text"]


async def test_the_agent_card_is_served_at_the_well_known_path(logger) -> None:
    async with http_client(_app(logger, ScriptedUseCase())) as client:
        response = await client.get("/.well-known/agent-card.json")

    assert response.status_code == 200
    card = response.json()
    assert card["name"] == "agent-runtime"
    assert card["supportedInterfaces"][0]["url"] == "http://test/a2a"
    [extension] = card["capabilities"]["extensions"]
    assert extension["uri"] == TURN_OPTIONS_URI
    assert extension["params"] == {"models": ["m"], "defaultModel": "m"}


async def test_a_message_is_answered_as_a_completed_task_in_its_conversation(logger) -> None:
    handle_message = ScriptedUseCase(ANSWERED)

    async with http_client(_app(logger, handle_message)) as client:
        task = await _task(client, _send("meaning?"))

    assert task["status"]["state"] == "TASK_STATE_COMPLETED"
    assert [artifact["parts"] for artifact in task["artifacts"]] == [[{"text": "42"}]]
    assert task["metadata"]["outcome"] == "answered"
    assert handle_message.requests[0].request_id == task["contextId"]


async def test_a_plan_waits_for_input_and_yes_finishes_the_same_task(logger) -> None:
    handle_message = ScriptedUseCase(PLANNED, ANSWERED)

    async with http_client(_app(logger, handle_message)) as client:
        planned = await _task(client, _send("count users"))
        approved = await _task(client, _send("yes", taskId=planned["id"]))
        again = await _post(client, _send("more", taskId=planned["id"]))

    assert planned["status"]["state"] == "TASK_STATE_INPUT_REQUIRED"
    assert _status_text(planned).endswith(APPROVAL_PROMPT)
    assert (approved["id"], approved["status"]["state"]) == (planned["id"], "TASK_STATE_COMPLETED")
    assert [request.request_id for request in handle_message.requests] == [planned["contextId"]] * 2
    assert [request.message for request in handle_message.requests] == ["count users", "yes"]
    assert again["error"]["code"] == -32004


async def test_a_streamed_message_sends_the_task_then_its_updates(logger) -> None:
    async with http_client(_app(logger, ScriptedUseCase(ANSWERED))) as client:
        body = _send("hi") | {"method": "SendStreamingMessage"}
        response = await client.post("/a2a", json=body, headers=VERSION)

    assert response.headers["content-type"].startswith("text/event-stream")
    frames = [
        json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
    ]
    results = [frame["result"] for frame in frames]
    assert {frame["id"] for frame in frames} == {"a"}
    assert "task" in results[0]
    working = [result["statusUpdate"] for result in results[1:-2]]
    assert {update["status"]["state"] for update in working} == {"TASK_STATE_WORKING"}
    assert _status_text(working[-1]) == "Comprehending the request"
    assert results[-2]["artifactUpdate"]["artifact"]["parts"] == [{"text": "42"}]
    assert results[-1]["statusUpdate"]["status"]["state"] == "TASK_STATE_COMPLETED"


async def test_a_running_task_can_be_followed_and_canceled(logger) -> None:
    handle_message = HangingUseCase()

    async with http_client(_app(logger, handle_message)) as client:
        task = await _task(client, _send("hi", {"returnImmediately": True}))
        await handle_message.started.wait()
        polled = await _polled(client, task["id"], "TASK_STATE_WORKING")
        canceled = await _task(client, _call("CancelTask", {"id": task["id"]}))

    assert polled["status"]["state"] == "TASK_STATE_WORKING"
    assert canceled["status"]["state"] == "TASK_STATE_CANCELED"
    await asyncio.wait_for(handle_message.cancelled.wait(), timeout=5)


async def test_a_full_server_fails_the_new_task(logger) -> None:
    handle_message = HangingUseCase()

    async with http_client(_app(logger, handle_message, max_concurrent_turns=1)) as client:
        first = await _task(client, _send("hi", {"returnImmediately": True}))
        await handle_message.started.wait()
        second = await _task(client, _send("hello"))
        await _task(client, _call("CancelTask", {"id": first["id"]}))

    assert second["status"]["state"] == "TASK_STATE_FAILED"
    assert _status_text(second) == AT_CAPACITY


async def test_a_message_without_text_is_rejected(logger) -> None:
    image = _send("x", parts=[{"url": "https://x/y.png"}])

    async with http_client(_app(logger, ScriptedUseCase())) as client:
        task = await _task(client, image)

    assert task["status"]["state"] == "TASK_STATE_REJECTED"
    assert _status_text(task) == TEXT_ONLY


async def test_the_model_and_auto_approve_come_from_the_message_metadata(logger) -> None:
    handle_message = ScriptedUseCase(ANSWERED)
    metadata = {"model": "small", "autoApprove": True}

    async with http_client(_app(logger, handle_message)) as client:
        await _task(client, _send("hi", metadata=metadata))

    [request] = handle_message.requests
    assert (request.model_name, request.auto_approve) == ("small", True)


async def test_the_extension_s_keys_choose_the_model_and_auto_approve(logger) -> None:
    handle_message = ScriptedUseCase(ANSWERED)
    metadata = {MODEL_KEY: "big", AUTO_APPROVE_KEY: True}

    async with http_client(_app(logger, handle_message)) as client:
        await _task(client, _send("hi", metadata=metadata))

    [request] = handle_message.requests
    assert (request.model_name, request.auto_approve) == ("big", True)


async def test_an_unknown_task_is_a_task_not_found_error(logger) -> None:
    async with http_client(_app(logger, ScriptedUseCase())) as client:
        reply = await _post(client, _call("GetTask", {"id": "missing"}))

    assert reply["error"]["code"] == -32001


async def test_the_sdk_s_own_client_gets_an_answer(logger) -> None:
    async with http_client(_app(logger, ScriptedUseCase(ANSWERED))) as http:
        config = ClientConfig(httpx_client=http, streaming=False)
        client = await create_client("http://test", client_config=config)
        message = new_text_message("meaning?", role=Role.ROLE_USER)
        responses = [
            response async for response in client.send_message(SendMessageRequest(message=message))
        ]

    task = responses[-1].task
    assert task.status.state == TaskState.TASK_STATE_COMPLETED
    assert task.artifacts[0].parts[0].text == "42"
