from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from agent_evaluation.domain.case import Case
from agent_evaluation.domain.check.check import CheckResult
from agent_evaluation.domain.exchange import Exchange
from agent_evaluation.domain.kind import Kind
from agent_evaluation.domain.reply import AgentReply
from agent_evaluation.domain.run_policy import RunPolicy
from agent_evaluation.domain.statistics import mean, percentile


class Status(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True, slots=True)
class ExchangeResult:
    exchange: Exchange
    checks: tuple[CheckResult, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


@dataclass(frozen=True, slots=True)
class RunResult:
    number: int
    status: Status
    run_id: str
    started_at: datetime
    seconds: float
    attempts: int
    exchanges: tuple[ExchangeResult, ...] = ()
    error: str = ""

    @property
    def failed_checks(self) -> tuple[CheckResult, ...]:
        return tuple(
            check for exchange in self.exchanges for check in exchange.checks if not check.passed
        )

    @property
    def replies(self) -> tuple[AgentReply, ...]:
        return tuple(exchange.exchange.reply for exchange in self.exchanges)


@dataclass(frozen=True, slots=True)
class CaseResult:
    case: Case
    status: Status
    runs: tuple[RunResult, ...] = ()
    reason: str = ""

    @classmethod
    def skipped(cls, case: Case, reason: str) -> CaseResult:
        return cls(case, Status.SKIPPED, reason=reason)

    @classmethod
    def from_runs(cls, case: Case, runs: tuple[RunResult, ...], pass_rate: float) -> CaseResult:
        passed = sum(run.status is Status.PASSED for run in runs)
        if runs and all(run.status is Status.ERROR for run in runs):
            return cls(case, Status.ERROR, runs, runs[-1].error)
        status = Status.PASSED if runs and passed / len(runs) >= pass_rate else Status.FAILED
        return cls(case, status, runs)

    @property
    def passed_runs(self) -> int:
        return sum(run.status is Status.PASSED for run in self.runs)

    @property
    def error_runs(self) -> int:
        return sum(run.status is Status.ERROR for run in self.runs)

    @property
    def pass_rate(self) -> float | None:
        return self.passed_runs / len(self.runs) if self.runs else None

    @property
    def is_flaky(self) -> bool:
        return 0 < self.passed_runs < len(self.runs)

    @property
    def replies(self) -> tuple[AgentReply, ...]:
        return tuple(reply for run in self.runs for reply in run.replies)


@dataclass(frozen=True, slots=True)
class KindResult:
    kind: Kind
    policy: RunPolicy
    cases: tuple[CaseResult, ...]
    started_at: datetime
    finished_at: datetime

    def count(self, status: Status) -> int:
        return sum(case.status is status for case in self.cases)

    @property
    def status(self) -> Status:
        executed = [case for case in self.cases if case.status is not Status.SKIPPED]
        if not executed:
            return Status.SKIPPED
        if any(case.status is Status.ERROR for case in executed):
            return Status.ERROR
        if any(case.status is Status.FAILED for case in executed):
            return Status.FAILED
        return Status.PASSED

    @property
    def executed(self) -> int:
        return len(self.cases) - self.count(Status.SKIPPED)

    @property
    def flaky(self) -> tuple[CaseResult, ...]:
        return tuple(case for case in self.cases if case.is_flaky)

    @property
    def runs(self) -> tuple[RunResult, ...]:
        return tuple(run for case in self.cases for run in case.runs)

    @property
    def run_pass_rate(self) -> float | None:
        runs = self.runs
        return sum(run.status is Status.PASSED for run in runs) / len(runs) if runs else None

    @property
    def replies(self) -> tuple[AgentReply, ...]:
        return tuple(reply for case in self.cases for reply in case.replies)

    @property
    def mean_seconds(self) -> float | None:
        return mean([reply.seconds for reply in self.replies])

    @property
    def p95_seconds(self) -> float | None:
        return percentile([reply.seconds for reply in self.replies], 95)

    @property
    def input_tokens(self) -> int:
        return sum(reply.input_tokens for reply in self.replies)

    @property
    def output_tokens(self) -> int:
        return sum(reply.output_tokens for reply in self.replies)

    @property
    def mean_judge_score(self) -> float | None:
        scores = [
            check.score
            for run in self.runs
            for exchange in run.exchanges
            for check in exchange.checks
            if check.score is not None
        ]
        return mean(scores)

    @property
    def failing_checks(self) -> list[tuple[str, int]]:
        tally = Counter(check.label for run in self.runs for check in run.failed_checks)
        return tally.most_common()
