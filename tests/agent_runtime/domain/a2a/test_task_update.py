from agent_runtime.domain.a2a.task_state import TaskState
from agent_runtime.domain.a2a.task_update import TaskUpdate
from agent_runtime.domain.event.turn_event import TurnEvent, TurnEventKind
from agent_runtime.domain.turn.answer import Answer
from agent_runtime.domain.workflow.step import Step


def test_a_step_or_a_token_is_work_in_progress() -> None:
    step = TurnEvent(TurnEventKind.STEP_STARTED, step=Step.PLAN)

    assert TaskUpdate.after(step) == TaskUpdate(TaskState.WORKING, step)
    assert TaskUpdate.after(TurnEvent.answer_delta("4")).state is TaskState.WORKING


def test_a_finished_turn_takes_the_state_of_its_answer() -> None:
    event = TurnEvent(TurnEventKind.FINISHED, answer=Answer.answered("42"))

    assert TaskUpdate.after(event) == TaskUpdate(TaskState.COMPLETED, event)


def test_a_failure_or_a_turn_without_an_answer_fails_the_task() -> None:
    assert TaskUpdate.after(TurnEvent.failed("down")).state is TaskState.FAILED
    assert TaskUpdate.after(TurnEvent(TurnEventKind.FINISHED)).state is TaskState.FAILED
    assert TaskUpdate.unanswered() == TaskUpdate(TaskState.FAILED)
