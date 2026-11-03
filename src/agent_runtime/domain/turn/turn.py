from __future__ import annotations

from dataclasses import dataclass, field

from agent_runtime.domain.tool.tool_call import ToolCall
from agent_runtime.domain.tool.tool_result import ToolResult
from agent_runtime.domain.turn.action import Action
from agent_runtime.domain.turn.answer import Answer
from agent_runtime.domain.turn.draft import Draft
from agent_runtime.domain.turn.feedback import Feedback
from agent_runtime.domain.turn.intent import Intent
from agent_runtime.domain.turn.pending_plan import PendingPlan
from agent_runtime.domain.turn.plan import Plan
from agent_runtime.domain.turn.plan_progress import PlanProgress
from agent_runtime.domain.turn.prior_run import PriorRun
from agent_runtime.domain.turn.screening import Screening
from agent_runtime.domain.turn.turn_options import TurnOptions
from agent_runtime.domain.turn.turn_settings import TurnSettings
from agent_runtime.domain.turn.understanding import Understanding
from agent_runtime.domain.turn.verdict import Verdict

WorkItem = Draft | ToolResult | Feedback


@dataclass
class Turn:
    request: str
    model: str
    settings: TurnSettings = field(default_factory=TurnSettings)
    options: TurnOptions = field(default_factory=TurnOptions)
    understanding: Understanding | None = None
    plan: Plan | None = None
    prior: PriorRun | None = None
    work: list[WorkItem] = field(default_factory=list)
    verdicts: list[Verdict] = field(default_factory=list)
    screening: Screening | None = None
    answer: Answer | None = None

    def understood(self, understanding: Understanding) -> None:
        self.understanding = understanding

    def execute(self, plan: Plan, prior: PriorRun | None = None) -> None:
        self.plan = plan
        self.prior = prior
        self.work = []
        self.verdicts = []

    def drafted(self, draft: Draft) -> None:
        self.work.append(draft)

    def observed(self, results: list[ToolResult]) -> None:
        self.work.extend(results)

    def reviewed(self, verdict: Verdict) -> None:
        self.verdicts.append(verdict)

    def screened(self, screening: Screening) -> None:
        self.screening = screening

    def refuse(self, reason: str) -> None:
        self.plan = None
        self.prior = None
        self.finish(Answer.refused(reason))

    def give_feedback(self, critique: str) -> None:
        self.work.append(Feedback(critique))

    def finish(self, answer: Answer) -> None:
        self.answer = answer

    def paused_plan(self) -> PendingPlan:
        progress = self.progress
        if progress is None or not self.is_resumable:
            raise ValueError("Only a turn that stopped short of its plan can be paused")
        run = self.prior or PriorRun(0)
        return PendingPlan(progress.plan, run.followed_by(progress.done, self.actions))

    def conclude(self) -> Answer:
        draft = self.last_draft
        if draft is None:
            return Answer.nothing()
        progress = self.progress
        if progress is not None and self.is_resumable:
            return Answer.plan_unfinished(progress)
        if draft.asks_for_tools:
            return Answer.budget_exhausted()
        if self.last_verdict is not None and self.last_verdict.rejects:
            return Answer.best_effort(draft.text)
        return Answer.answered(draft.text)

    @property
    def query(self) -> str:
        return self.understanding.query if self.understanding else self.request

    @property
    def intent(self) -> Intent | None:
        return self.understanding.intent if self.understanding else None

    @property
    def drafts(self) -> list[Draft]:
        return [item for item in self.work if isinstance(item, Draft)]

    @property
    def evidence(self) -> list[ToolResult]:
        return [item for item in self.work if isinstance(item, ToolResult)]

    @property
    def progress(self) -> PlanProgress | None:
        if self.plan is None:
            return None
        return PlanProgress.of(self.plan, self.evidence, done=self.prior.done if self.prior else 0)

    @property
    def leaves_plan_unfinished(self) -> bool:
        progress = self.progress
        return progress is not None and not progress.is_complete

    @property
    def ran_out_of_steps(self) -> bool:
        draft = self.last_draft
        keeps_working = draft is not None and (draft.asks_for_tools or self.leaves_plan_unfinished)
        return keeps_working and self.steps_taken >= self.settings.max_steps

    @property
    def is_resumable(self) -> bool:
        return self.leaves_plan_unfinished or (self.plan is not None and self.ran_out_of_steps)

    @property
    def actions(self) -> list[Action]:
        actions: list[Action] = []
        calls: dict[str, ToolCall] = {}
        for item in self.work:
            if isinstance(item, Draft):
                calls = {call.id: call for call in item.tool_calls}
            elif isinstance(item, ToolResult) and item.call_id in calls:
                actions.append(Action.of(calls[item.call_id], item))
        return actions

    @property
    def last_draft(self) -> Draft | None:
        drafts = self.drafts
        return drafts[-1] if drafts else None

    @property
    def last_verdict(self) -> Verdict | None:
        return self.verdicts[-1] if self.verdicts else None

    @property
    def steps_taken(self) -> int:
        return len(self.drafts)

    @property
    def retries(self) -> int:
        return sum(1 for item in self.work if isinstance(item, Feedback))

    @property
    def used_tools(self) -> bool:
        return bool(self.evidence)

    @property
    def is_plain_direct_answer(self) -> bool:
        return self.intent is Intent.DIRECT and not self.used_tools
