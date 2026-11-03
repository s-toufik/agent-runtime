from dataclasses import dataclass

from agent_evaluation.application.kind_suite import KindSuite
from agent_evaluation.domain.capability import Capabilities
from agent_evaluation.domain.case import Case
from agent_evaluation.domain.run_policy import RunPolicy


@dataclass(frozen=True, slots=True)
class PlannedCase:
    case: Case
    runs: int
    skip_reason: str | None

    @property
    def requests(self) -> int:
        return 0 if self.skip_reason else self.runs * len(self.case.says)

    @property
    def judge_calls(self) -> int:
        return 0 if self.skip_reason else self.runs * self.case.judged_checks


@dataclass(frozen=True, slots=True)
class PlannedKind:
    suite: KindSuite
    cases: tuple[PlannedCase, ...]

    @property
    def active(self) -> tuple[PlannedCase, ...]:
        return tuple(planned for planned in self.cases if planned.skip_reason is None)

    @property
    def requests(self) -> int:
        return sum(planned.requests for planned in self.cases)

    @property
    def judge_calls(self) -> int:
        return sum(planned.judge_calls for planned in self.cases)

    @property
    def pause_seconds(self) -> float:
        base: RunPolicy = self.suite.policy
        total = max(0, len(self.active) - 1) * base.pause_between_cases_seconds
        for planned in self.active:
            policy = base.for_case(planned.case)
            messages = planned.runs * (len(planned.case.says) - 1)
            total += (planned.runs - 1) * policy.pause_between_runs_seconds
            total += messages * policy.pause_between_messages_seconds
        return total


class EvaluationPlan:
    def __init__(self, suites: tuple[KindSuite, ...], capabilities: Capabilities) -> None:
        self.kinds: tuple[PlannedKind, ...] = tuple(
            PlannedKind(
                suite,
                tuple(
                    PlannedCase(
                        case,
                        suite.policy.for_case(case).runs,
                        suite.skip_reason(case, capabilities),
                    )
                    for case in suite.cases
                ),
            )
            for suite in suites
        )

    @property
    def requests(self) -> int:
        return sum(kind.requests for kind in self.kinds)

    @property
    def judge_calls(self) -> int:
        return sum(kind.judge_calls for kind in self.kinds)

    @property
    def pause_seconds(self) -> float:
        return sum(kind.pause_seconds for kind in self.kinds)

    def describe(self) -> list[str]:
        lines: list[str] = []
        for kind in self.kinds:
            policy = kind.suite.policy
            lines.append(
                f"{kind.suite.kind}: {len(kind.active)}/{len(kind.cases)} cases, "
                f"{policy.forced_runs or policy.runs} runs each by default, "
                f"{kind.requests} requests, "
                f"{kind.judge_calls} judge calls"
            )
            for planned in kind.cases:
                state = (
                    f"skipped: {planned.skip_reason}"
                    if planned.skip_reason
                    else f"{planned.runs} runs x {len(planned.case.says)} messages"
                )
                lines.append(f"  - {planned.case.id}: {state}")
        lines.append(
            f"Total: {self.requests} agent requests, {self.judge_calls} judge calls, "
            f"at least {_duration(self.pause_seconds)} of pauses"
        )
        return lines


def _duration(seconds: float) -> str:
    minutes, rest = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m {rest:02d}s" if hours else f"{minutes}m {rest:02d}s"
