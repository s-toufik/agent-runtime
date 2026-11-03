from dataclasses import dataclass, replace

from agent_evaluation.domain.case import Case


@dataclass(frozen=True, slots=True)
class RunPolicy:
    runs: int
    pause_between_runs_seconds: float
    pause_between_messages_seconds: float
    pause_between_cases_seconds: float
    retry_on_error: int
    retry_pause_seconds: float
    case_pass_rate: float
    forced_runs: int | None = None
    forced_pause_between_runs_seconds: float | None = None

    def for_case(self, case: Case) -> RunPolicy:
        return replace(
            self,
            runs=_first(self.forced_runs, case.runs, self.runs),
            pause_between_runs_seconds=_first(
                self.forced_pause_between_runs_seconds,
                case.pause_between_runs_seconds,
                self.pause_between_runs_seconds,
            ),
        )


def _first[T](*values: T | None) -> T:
    return next(value for value in values if value is not None)
