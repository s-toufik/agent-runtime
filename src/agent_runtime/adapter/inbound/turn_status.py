from agent_runtime.domain.event.turn_event import TurnEvent
from agent_runtime.domain.workflow.step import Step

DELEGATE_TASKS: str = "delegate_tasks"
STEP_STATUS: dict[Step, str] = {
    Step.UNDERSTAND: "Comprehending the request",
    Step.PLAN: "Formulating a plan",
    Step.REVIEW: "Reviewing the answer",
}


def step_status(event: TurnEvent) -> str | None:
    if event.step is Step.RUN_TOOLS:
        others = [tool for tool in event.tools if tool != DELEGATE_TASKS]
        if len(others) < len(event.tools) and not others:
            return "Handing tasks to other agents"
        names = ", ".join(event.tools).replace(DELEGATE_TASKS, "other agents")
        return f"Running {names}"
    return STEP_STATUS.get(event.step) if event.step else None
