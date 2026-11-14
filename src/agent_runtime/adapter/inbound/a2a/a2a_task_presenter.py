from a2a.helpers import new_text_part
from a2a.server.tasks import TaskUpdater
from a2a.types.a2a_pb2 import TaskState as SdkTaskState

from agent_runtime.adapter.inbound.turn_status import step_status
from agent_runtime.domain.a2a.task_state import TaskState
from agent_runtime.domain.a2a.task_update import TaskUpdate
from agent_runtime.domain.event.turn_event import TurnEvent, TurnEventKind
from agent_runtime.domain.turn.outcome import Outcome

ANSWER_ARTIFACT: str = "answer"
APPROVAL_PROMPT: str = (
    'Reply "yes" in this task to approve the plan, "Drop plan" to cancel it, or say what to change.'
)
NO_ANSWER: str = "The turn ended without an answer."

SDK_STATES: dict[TaskState, SdkTaskState] = {
    TaskState.WORKING: SdkTaskState.TASK_STATE_WORKING,
    TaskState.INPUT_REQUIRED: SdkTaskState.TASK_STATE_INPUT_REQUIRED,
    TaskState.COMPLETED: SdkTaskState.TASK_STATE_COMPLETED,
    TaskState.FAILED: SdkTaskState.TASK_STATE_FAILED,
    TaskState.REJECTED: SdkTaskState.TASK_STATE_REJECTED,
}


class A2aTaskPresenter:
    async def present(self, updater: TaskUpdater, update: TaskUpdate) -> None:
        event: TurnEvent | None = update.event
        if update.state is TaskState.WORKING:
            status = (
                step_status(event) if event and event.kind is TurnEventKind.STEP_STARTED else None
            )
            if status:
                await updater.start_work(_message(updater, status))
            return

        if update.state is TaskState.COMPLETED:
            await updater.add_artifact(
                [new_text_part(_answer_text(event))], name=ANSWER_ARTIFACT, last_chunk=True
            )
            await updater.update_status(SDK_STATES[update.state], metadata=_metadata(event))
            return

        await updater.update_status(
            SDK_STATES[update.state],
            _message(updater, _status_text(update.state, event)),
            metadata=_metadata(event),
        )


def _message(updater: TaskUpdater, text: str):
    return updater.new_agent_message([new_text_part(text)])


def _answer_text(event: TurnEvent | None) -> str:
    return event.answer.text if event and event.answer else ""


def _status_text(state: TaskState, event: TurnEvent | None) -> str:
    if state is TaskState.FAILED:
        return event.error if event and event.error else NO_ANSWER
    text = _answer_text(event)
    if event and event.answer and event.answer.outcome is Outcome.AWAITING_APPROVAL:
        return f"{text}\n\n---\n{APPROVAL_PROMPT}"
    return text


def _metadata(event: TurnEvent | None) -> dict[str, str] | None:
    if event is None or event.kind is not TurnEventKind.FINISHED:
        return None
    fields: dict[str, str] = {}
    if event.answer is not None:
        fields["outcome"] = str(event.answer.outcome)
    if event.model:
        fields["model"] = event.model
    if event.usage is not None:
        fields["inputTokens"] = str(event.usage.input_tokens)
        fields["outputTokens"] = str(event.usage.output_tokens)
    if event.tools:
        fields["tools"] = ", ".join(event.tools)
    return fields or None
