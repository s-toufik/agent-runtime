from __future__ import annotations

from dataclasses import dataclass

from agent_runtime.domain.turn.plan import Plan
from agent_runtime.domain.turn.plan_progress import PlanProgress
from agent_runtime.domain.turn.prior_run import PriorRun

PAUSED: str = "### Plan paused at the step limit (✓ done, → where it stopped, · still to do)"


@dataclass(frozen=True, slots=True)
class PendingPlan:
    plan: Plan
    prior: PriorRun | None = None

    @property
    def is_paused(self) -> bool:
        return self.prior is not None

    def render(self) -> str:
        if self.prior is None:
            return self.plan.render()
        progress = PlanProgress(self.plan, self.prior.done)
        return "\n".join([PAUSED, progress.render(), *self.plan.render_expected_result()])
