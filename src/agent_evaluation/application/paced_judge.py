from collections.abc import Sequence

from agent_evaluation.application.port.clock import Clock
from agent_evaluation.domain.check.judge import Grade, Judge
from agent_evaluation.domain.exchange import Exchange


class PacedJudge:
    def __init__(self, judge: Judge, clock: Clock, pause_seconds: float) -> None:
        self._judge = judge
        self._clock = clock
        self._pause_seconds = pause_seconds

    async def grade(self, criterion: str, transcript: Sequence[Exchange]) -> Grade:
        if self._pause_seconds > 0:
            await self._clock.sleep(self._pause_seconds)
        return await self._judge.grade(criterion, transcript)
