from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from agent_evaluation.domain.exchange import Exchange


@dataclass(frozen=True, slots=True)
class Grade:
    score: float
    reason: str


class Judge(Protocol):
    async def grade(self, criterion: str, transcript: Sequence[Exchange]) -> Grade: ...
