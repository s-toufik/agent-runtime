import asyncio
from contextlib import aclosing

from agent_runtime.adapter.outbound.event.queue_turn_event_stream import QueueTurnEventStream
from agent_runtime.application.use_case.run_a2a_task import RunA2aTask
from agent_runtime.domain.a2a.a2a_task_request import A2aTaskRequest
from agent_runtime.domain.a2a.task_state import TaskState
from agent_runtime.domain.event.turn_event import TurnEvent, TurnEventKind
from agent_runtime.domain.workflow.step import Step
from tests.support.a2a import ANSWERED, HangingUseCase, Models, ScriptedUseCase, listing_of

REQUEST = A2aTaskRequest(text="meaning?", context_id="c7")


def _use_case(handle_message) -> RunA2aTask:
    return RunA2aTask(handle_message, QueueTurnEventStream, Models(listing_of("m", "big")))


async def test_a_turn_is_reported_as_task_updates_in_the_task_s_conversation() -> None:
    handle_message = ScriptedUseCase(ANSWERED)

    updates = [update async for update in _use_case(handle_message).run(REQUEST)]

    assert [update.state for update in updates] == [TaskState.WORKING, TaskState.COMPLETED]
    [request] = handle_message.requests
    assert (request.message, request.request_id, request.auto_approve) == ("meaning?", "c7", False)


async def test_a_turn_that_ends_without_an_answer_fails_the_task() -> None:
    started = [TurnEvent(TurnEventKind.STEP_STARTED, step=Step.UNDERSTAND)]

    updates = [update async for update in _use_case(ScriptedUseCase(started)).run(REQUEST)]

    assert [update.state for update in updates] == [TaskState.WORKING, TaskState.FAILED]
    assert updates[-1].event is None


async def test_the_model_comes_from_the_request_else_the_first_listed() -> None:
    handle_message = ScriptedUseCase(ANSWERED, ANSWERED)
    chosen = A2aTaskRequest(text="hi", context_id="c", model_name="small")

    for request in (REQUEST, chosen):
        [_ async for _ in _use_case(handle_message).run(request)]

    assert [request.model_name for request in handle_message.requests] == ["m", "small"]


async def test_auto_approve_is_passed_on() -> None:
    handle_message = ScriptedUseCase(ANSWERED)
    request = A2aTaskRequest(text="hi", context_id="c", auto_approve=True)

    [_ async for _ in _use_case(handle_message).run(request)]

    assert handle_message.requests[0].auto_approve is True


async def test_stopping_the_updates_cancels_the_turn() -> None:
    handle_message = HangingUseCase()

    async with aclosing(_use_case(handle_message).run(REQUEST)) as updates:
        waiting = asyncio.create_task(anext(updates))
        await handle_message.started.wait()
        waiting.cancel()
        await asyncio.gather(waiting, return_exceptions=True)

    await asyncio.wait_for(handle_message.cancelled.wait(), timeout=5)
