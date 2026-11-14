from enum import StrEnum

from agent_runtime.domain.turn.answer import Answer
from agent_runtime.domain.turn.outcome import Outcome


class TaskState(StrEnum):
    WORKING = "working"
    INPUT_REQUIRED = "input_required"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"

    @classmethod
    def of(cls, answer: Answer) -> TaskState:
        match answer.outcome:
            case Outcome.ANSWERED | Outcome.BEST_EFFORT:
                return cls.COMPLETED
            case Outcome.AWAITING_APPROVAL | Outcome.CLARIFICATION:
                return cls.INPUT_REQUIRED
            case Outcome.BUDGET_EXHAUSTED:
                return cls.INPUT_REQUIRED if answer.resumable else cls.COMPLETED
            case Outcome.REFUSED:
                return cls.REJECTED

    @property
    def ends_the_turn(self) -> bool:
        return self is not TaskState.WORKING
