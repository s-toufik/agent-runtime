import asyncio
import json
from collections.abc import AsyncIterator

import pytest
from pycraftcore.web.sse import SSE_HEARTBEAT

from agent_runtime.adapter.inbound.web.exception.server_at_capacity_exception import (
    ServerAtCapacityException,
)
from agent_runtime.adapter.inbound.web.stream.stream_agent_controller import (
    StreamAgentController,
)
from agent_runtime.adapter.outbound.event.queue_turn_event_stream import QueueTurnEventStream
from agent_runtime.domain.event.turn_event import TurnEvent
from agent_runtime.domain.request.agent_request import AgentRequest
from agent_runtime.domain.turn.answer import Answer
from agent_runtime.domain.turn.turn import Turn
from agent_runtime.domain.turn.turn_settings import TurnSettings
from agent_runtime.domain.workflow.step import Step

REQUEST = AgentRequest(message="hi", model_name="m", request_id="r1")


class ScriptedUseCase:
    def __init__(self, events: list[TurnEvent]) -> None:
        self._events = events

    async def handle(self, request, events) -> None:
        for event in self._events:
            await events.publish(event)
        await events.complete()


class HangingUseCase:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def handle(self, request, events) -> None:
        self.started.set()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            self.cancelled.set()
            raise


def _finished(text: str) -> TurnEvent:
    turn = Turn(request="hi", model="m", settings=TurnSettings(max_steps=6))
    turn.finish(Answer.answered(text))
    return TurnEvent.finished(turn)


async def _drain(stream: AsyncIterator[bytes]) -> list[str]:
    return [chunk.decode("utf-8") async for chunk in stream]


async def test_a_turn_streams_its_status_then_the_answer_then_complete(logger) -> None:
    turn = Turn(request="hi", model="m")
    events = [
        TurnEvent.entering(Step.UNDERSTAND, turn),
        TurnEvent.answer_delta("Hel"),
        _finished("Hello"),
    ]
    controller = StreamAgentController(ScriptedUseCase(events), QueueTurnEventStream, logger)

    chunks = await _drain(await controller.execute(REQUEST))

    assert "event: status" in chunks[0] and "Comprehending the request" in chunks[0]
    assert "event: token" in chunks[1] and "Hel" in chunks[1]
    assert "event: final" in chunks[2]
    final_payload = json.loads(chunks[2].split("\n")[1].removeprefix("data: "))
    assert final_payload["content"] == "Hello"
    assert final_payload["session_id"] == "r1"
    assert final_payload["metadata"] == {
        "iteration": "0",
        "max_iteration": "6",
        "outcome": "answered",
        "model": "m",
    }
    assert "event: complete" in chunks[3]


async def test_admission_is_released_after_a_stream_completes(logger) -> None:
    controller = StreamAgentController(
        ScriptedUseCase([]), QueueTurnEventStream, logger, max_concurrent_streams=1
    )

    await _drain(await controller.execute(REQUEST))
    await _drain(await controller.execute(REQUEST))


async def test_admission_is_released_when_setup_itself_raises(logger) -> None:
    def broken_stream_events():
        raise RuntimeError("queue construction failed")

    controller = StreamAgentController(
        ScriptedUseCase([]), broken_stream_events, logger, max_concurrent_streams=1
    )

    with pytest.raises(RuntimeError, match="queue construction failed"):
        await controller.execute(REQUEST)

    await asyncio.wait_for(controller._admission.acquire(), timeout=1)


async def test_rejects_when_at_capacity(logger) -> None:
    controller = StreamAgentController(
        ScriptedUseCase([]), QueueTurnEventStream, logger, max_concurrent_streams=1
    )
    await controller._admission.acquire()

    with pytest.raises(ServerAtCapacityException, match="capacity"):
        await controller.execute(REQUEST)

    assert logger.messages("warning")


async def test_a_heartbeat_is_sent_while_the_turn_is_silent(logger) -> None:
    use_case = HangingUseCase()
    controller = StreamAgentController(
        use_case, QueueTurnEventStream, logger, heartbeat_seconds=0.01
    )
    stream = await controller.execute(REQUEST)

    first = await anext(stream)
    await stream.aclose()

    assert first == SSE_HEARTBEAT


async def test_closing_the_stream_cancels_the_use_case_and_releases_admission(logger) -> None:
    use_case = HangingUseCase()
    controller = StreamAgentController(
        use_case, QueueTurnEventStream, logger, max_concurrent_streams=1, heartbeat_seconds=0.01
    )
    stream = await controller.execute(REQUEST)
    await anext(stream)
    await use_case.started.wait()

    await stream.aclose()  # what the web framework does when the client goes away

    assert use_case.cancelled.is_set()
    assert logger.messages("warning")
    await asyncio.wait_for(controller._admission.acquire(), timeout=1)


async def test_cancelling_the_stream_cancels_the_use_case(logger) -> None:
    use_case = HangingUseCase()
    controller = StreamAgentController(use_case, QueueTurnEventStream, logger)
    stream = await controller.execute(REQUEST)

    consumer = asyncio.create_task(_drain(stream))
    await use_case.started.wait()
    consumer.cancel()

    with pytest.raises(asyncio.CancelledError):
        await consumer
    assert use_case.cancelled.is_set()


async def test_an_unexpected_error_yields_an_error_frame_then_reraises(logger) -> None:
    class BrokenEvents:
        async def publish(self, event: TurnEvent) -> None: ...
        async def complete(self) -> None: ...

        async def __aiter__(self) -> AsyncIterator[TurnEvent]:
            raise RuntimeError("queue broke")
            yield  # pragma: no cover

    controller = StreamAgentController(ScriptedUseCase([]), BrokenEvents, logger)

    chunks = []
    with pytest.raises(RuntimeError, match="queue broke"):
        async for chunk in await controller.execute(REQUEST):
            chunks.append(chunk.decode("utf-8"))

    assert len(chunks) == 1
    assert "event: error" in chunks[0]
    payload = json.loads(chunks[0].split("\n")[1].removeprefix("data: "))
    assert payload["type"] == "error"
    assert "queue broke" in payload["content"]
    assert logger.messages("error")
