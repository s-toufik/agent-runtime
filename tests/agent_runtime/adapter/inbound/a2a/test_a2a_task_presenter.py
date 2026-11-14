from typing import Any, cast

import pytest
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types.a2a_pb2 import TaskArtifactUpdateEvent, TaskState, TaskStatusUpdateEvent
from google.protobuf import json_format

from agent_runtime.adapter.inbound.a2a.a2a_task_presenter import (
    APPROVAL_PROMPT,
    NO_ANSWER,
    A2aTaskPresenter,
)
from agent_runtime.domain.a2a.task_update import TaskUpdate
from agent_runtime.domain.event.turn_event import TurnEvent, TurnEventKind
from agent_runtime.domain.turn.outcome import Outcome
from agent_runtime.domain.workflow.step import Step
from tests.support.a2a import finished


class RecordingQueue:
    def __init__(self) -> None:
        self.events: list[Any] = []

    async def enqueue_event(self, event: Any) -> None:
        self.events.append(event)


async def _present(*updates: TaskUpdate) -> list[Any]:
    queue = RecordingQueue()
    updater = TaskUpdater(cast(EventQueue, queue), "t1", "c1")
    for update in updates:
        await A2aTaskPresenter().present(updater, update)
    return queue.events


def _text(event: TaskStatusUpdateEvent) -> str:
    return event.status.message.parts[0].text


async def test_a_started_step_is_a_working_status_with_its_label() -> None:
    [event] = await _present(
        TaskUpdate.after(TurnEvent(TurnEventKind.STEP_STARTED, step=Step.UNDERSTAND))
    )

    assert event.status.state == TaskState.TASK_STATE_WORKING
    assert _text(event) == "Comprehending the request"


async def test_tokens_and_unlabelled_steps_send_nothing() -> None:
    silent = TurnEvent(TurnEventKind.STEP_STARTED, step=Step.SCREEN)

    assert (
        await _present(TaskUpdate.after(silent), TaskUpdate.after(TurnEvent.answer_delta("4")))
        == []
    )


async def test_an_answer_is_an_artifact_then_a_completed_status_with_the_turn_s_metadata() -> None:
    artifact, status = await _present(TaskUpdate.after(finished("42")))

    assert isinstance(artifact, TaskArtifactUpdateEvent)
    assert artifact.artifact.name == "answer"
    assert artifact.artifact.parts[0].text == "42"
    assert artifact.last_chunk is True
    assert status.status.state == TaskState.TASK_STATE_COMPLETED
    assert json_format.MessageToDict(status.metadata) == {
        "outcome": "answered",
        "model": "m",
        "inputTokens": "3",
        "outputTokens": "2",
    }


async def test_a_plan_asks_for_input_with_the_approval_prompt() -> None:
    [status] = await _present(TaskUpdate.after(finished("### Plan", Outcome.AWAITING_APPROVAL)))

    assert status.status.state == TaskState.TASK_STATE_INPUT_REQUIRED
    assert _text(status) == f"### Plan\n\n---\n{APPROVAL_PROMPT}"


@pytest.mark.parametrize(
    ("update", "state", "text"),
    [
        (TaskUpdate.after(finished("no", Outcome.REFUSED)), TaskState.TASK_STATE_REJECTED, "no"),
        (TaskUpdate.after(TurnEvent.failed("down")), TaskState.TASK_STATE_FAILED, "down"),
        (TaskUpdate.unanswered(), TaskState.TASK_STATE_FAILED, NO_ANSWER),
    ],
)
async def test_a_refusal_or_a_failure_ends_the_task_with_its_reason(update, state, text) -> None:
    [status] = await _present(update)

    assert status.status.state == state
    assert _text(status) == text
