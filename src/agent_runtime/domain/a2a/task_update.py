from dataclasses import dataclass

from agent_runtime.domain.a2a.task_state import TaskState
from agent_runtime.domain.event.turn_event import TurnEvent, TurnEventKind


@dataclass(frozen=True, slots=True)
class TaskUpdate:
    state: TaskState
    event: TurnEvent | None = None

    @classmethod
    def after(cls, event: TurnEvent) -> TaskUpdate:
        match event.kind:
            case TurnEventKind.STEP_STARTED | TurnEventKind.ANSWER_DELTA:
                return cls(TaskState.WORKING, event)
            case TurnEventKind.FAILED:
                return cls(TaskState.FAILED, event)
            case TurnEventKind.FINISHED:
                if event.answer is None:
                    return cls(TaskState.FAILED, event)
                return cls(TaskState.of(event.answer), event)

    @classmethod
    def unanswered(cls) -> TaskUpdate:
        return cls(TaskState.FAILED)
