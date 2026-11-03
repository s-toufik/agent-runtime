from dataclasses import dataclass

from agent_evaluation.domain.check.check import Check
from agent_evaluation.domain.check.judged import Judged

MAIN_CONVERSATION: str = "main"


@dataclass(frozen=True, slots=True)
class Say:
    message: str
    expect: tuple[Check, ...] = ()
    auto_approve: bool = False
    conversation: str = MAIN_CONVERSATION

    @property
    def judged_checks(self) -> int:
        return sum(isinstance(check, Judged) for check in self.expect)


@dataclass(frozen=True, slots=True)
class Case:
    id: str
    title: str
    says: tuple[Say, ...]
    requires: tuple[str, ...] = ()
    unless: tuple[str, ...] = ()
    runs: int | None = None
    pause_between_runs_seconds: float | None = None

    @property
    def capabilities(self) -> tuple[str, ...]:
        return (*self.requires, *self.unless)

    @property
    def judged_checks(self) -> int:
        return sum(say.judged_checks for say in self.says)
