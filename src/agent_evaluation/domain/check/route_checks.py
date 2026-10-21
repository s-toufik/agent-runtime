from dataclasses import dataclass

from agent_evaluation.domain.check.check import CheckContext, CheckResult


def _statuses(context: CheckContext) -> str:
    return f"statuses: {' | '.join(context.reply.statuses) or 'none'}"


@dataclass(frozen=True, slots=True)
class ShowsPlanStep:
    @property
    def label(self) -> str:
        return "goes through planning"

    async def verify(self, context: CheckContext) -> CheckResult:
        passed = context.rules.markers.plan_status in context.reply.statuses
        return CheckResult(self.label, passed, _statuses(context))


@dataclass(frozen=True, slots=True)
class SkipsPlanStep:
    @property
    def label(self) -> str:
        return "skips planning"

    async def verify(self, context: CheckContext) -> CheckResult:
        passed = context.rules.markers.plan_status not in context.reply.statuses
        return CheckResult(self.label, passed, _statuses(context))
