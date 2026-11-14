import pytest

from agent_runtime.domain.a2a.task_state import TaskState
from agent_runtime.domain.turn.answer import Answer
from agent_runtime.domain.turn.outcome import Outcome


@pytest.mark.parametrize(
    ("outcome", "resumable", "state"),
    [
        (Outcome.ANSWERED, False, TaskState.COMPLETED),
        (Outcome.BEST_EFFORT, False, TaskState.COMPLETED),
        (Outcome.AWAITING_APPROVAL, False, TaskState.INPUT_REQUIRED),
        (Outcome.CLARIFICATION, False, TaskState.INPUT_REQUIRED),
        (Outcome.BUDGET_EXHAUSTED, True, TaskState.INPUT_REQUIRED),
        (Outcome.BUDGET_EXHAUSTED, False, TaskState.COMPLETED),
        (Outcome.REFUSED, False, TaskState.REJECTED),
    ],
)
def test_each_outcome_gives_a_task_state(outcome, resumable, state) -> None:
    assert TaskState.of(Answer("x", outcome, resumable)) is state


def test_only_working_keeps_the_turn_going() -> None:
    assert [state for state in TaskState if not state.ends_the_turn] == [TaskState.WORKING]
