from dataclasses import dataclass

from agent_evaluation.domain.check.check import CheckContext, CheckResult


@dataclass(frozen=True, slots=True)
class Judged:
    criterion: str
    min_score: float | None = None

    @property
    def label(self) -> str:
        short = self.criterion if len(self.criterion) <= 90 else f"{self.criterion[:87]}..."
        return f"judge: {short}"

    async def verify(self, context: CheckContext) -> CheckResult:
        grade = await context.judge.grade(context.render(self.criterion), context.history)
        threshold = self.min_score if self.min_score is not None else context.rules.pass_score
        return CheckResult(self.label, grade.score >= threshold, grade.reason, grade.score)
