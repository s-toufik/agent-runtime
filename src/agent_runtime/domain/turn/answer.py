from __future__ import annotations

from dataclasses import dataclass

from agent_runtime.domain.turn.outcome import Outcome
from agent_runtime.domain.turn.plan import Plan
from agent_runtime.domain.turn.plan_progress import PlanProgress

NO_ANSWER: str = "No answer was produced."
BUDGET_EXHAUSTED: str = (
    "I reached the step limit before finishing this task. "
    "Ask me to continue, or narrow the request."
)
PLAN_UNFINISHED: str = (
    "I reached the step limit before finishing the plan:\n\n{progress}\n\n"
    "Ask me to continue, or narrow the request."
)
NO_PLAN: str = "I could not write a plan for this request. Try rephrasing it."

REFUSED: str = "[SCREEN]: {reason}"


@dataclass(frozen=True, slots=True)
class Answer:
    text: str
    outcome: Outcome
    resumable: bool = False

    @classmethod
    def answered(cls, text: str) -> Answer:
        return cls(text, Outcome.ANSWERED)

    @classmethod
    def best_effort(cls, text: str) -> Answer:
        return cls(text, Outcome.BEST_EFFORT)

    @classmethod
    def nothing(cls) -> Answer:
        return cls(NO_ANSWER, Outcome.BEST_EFFORT)

    @classmethod
    def budget_exhausted(cls) -> Answer:
        return cls(BUDGET_EXHAUSTED, Outcome.BUDGET_EXHAUSTED)

    @classmethod
    def plan_unfinished(cls, progress: PlanProgress) -> Answer:
        text = PLAN_UNFINISHED.format(progress=progress.render())
        return cls(text, Outcome.BUDGET_EXHAUSTED, resumable=True)

    @classmethod
    def approval_request(cls, plan: Plan) -> Answer:
        return cls(plan.render(), Outcome.AWAITING_APPROVAL)

    @classmethod
    def no_plan(cls) -> Answer:
        return cls(NO_PLAN, Outcome.BEST_EFFORT)

    @classmethod
    def clarification(cls, question: str) -> Answer:
        return cls(question, Outcome.CLARIFICATION)

    @classmethod
    def refused(cls, reason: str) -> Answer:
        return cls(REFUSED.format(reason=reason), Outcome.REFUSED)
