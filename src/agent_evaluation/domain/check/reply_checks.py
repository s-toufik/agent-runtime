from dataclasses import dataclass

from agent_evaluation.domain.check.check import CheckContext, CheckResult
from agent_evaluation.domain.outcome import Outcome


@dataclass(frozen=True, slots=True)
class Completes:
    @property
    def label(self) -> str:
        return "the agent replies without error"

    async def verify(self, context: CheckContext) -> CheckResult:
        reply = context.reply
        if reply.errors:
            return CheckResult(self.label, False, f"error event: {reply.errors[0][:300]}")
        if not reply.content.strip():
            return CheckResult(self.label, False, "the answer is empty")
        return CheckResult(self.label, True)


@dataclass(frozen=True, slots=True, init=False)
class OutcomeIs:
    outcomes: tuple[Outcome, ...]

    def __init__(self, *outcomes: Outcome) -> None:
        object.__setattr__(self, "outcomes", outcomes)

    @property
    def label(self) -> str:
        return f"outcome is {' or '.join(self.outcomes)}"

    async def verify(self, context: CheckContext) -> CheckResult:
        outcome = context.reply.outcome
        return CheckResult(self.label, outcome in self.outcomes, f"outcome: {outcome or 'none'}")


@dataclass(frozen=True, slots=True, init=False)
class OutcomeIsNot:
    outcomes: tuple[Outcome, ...]

    def __init__(self, *outcomes: Outcome) -> None:
        object.__setattr__(self, "outcomes", outcomes)

    @property
    def label(self) -> str:
        return f"outcome is not {' or '.join(self.outcomes)}"

    async def verify(self, context: CheckContext) -> CheckResult:
        outcome = context.reply.outcome
        return CheckResult(
            self.label, outcome not in self.outcomes, f"outcome: {outcome or 'none'}"
        )


@dataclass(frozen=True, slots=True)
class Answers:
    @property
    def label(self) -> str:
        return "the agent answers (answered or best effort)"

    async def verify(self, context: CheckContext) -> CheckResult:
        outcome = context.reply.outcome
        passed = outcome in (Outcome.ANSWERED, Outcome.BEST_EFFORT)
        return CheckResult(self.label, passed, f"outcome: {outcome or 'none'}")
