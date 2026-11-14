from agent_runtime.domain.event.turn_event import TurnEvent
from agent_runtime.domain.workflow.step import Step

STEP_STATUS: dict[Step, str] = {
    Step.UNDERSTAND: "Comprehending the request",
    Step.PLAN: "Formulating a plan",
    Step.REVIEW: "Reviewing the answer",
}


def step_status(event: TurnEvent) -> str | None:
    if event.step is Step.RUN_TOOLS:
        return f"Running {', '.join(event.tools)}"
    return STEP_STATUS.get(event.step) if event.step else None
