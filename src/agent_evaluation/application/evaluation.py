import logging
from dataclasses import dataclass
from pathlib import Path

from agent_evaluation.application.kind_evaluator import KindEvaluator
from agent_evaluation.application.kind_suite import KindSuite
from agent_evaluation.application.port.agent import Agent
from agent_evaluation.application.port.clock import Clock
from agent_evaluation.application.port.report_writer import KindJournal, ReportWriter
from agent_evaluation.domain.result import KindResult, Status

logger: logging.Logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EvaluationOutcome:
    results: tuple[KindResult, ...]
    files: tuple[Path, ...]
    overall: Path


class Evaluation:
    def __init__(
        self,
        agent: Agent,
        evaluator: KindEvaluator,
        writer: ReportWriter,
        journal: KindJournal,
        clock: Clock,
    ) -> None:
        self._agent = agent
        self._evaluator = evaluator
        self._writer = writer
        self._journal = journal
        self._clock = clock

    async def run(self, suites: tuple[KindSuite, ...]) -> EvaluationOutcome:
        await self._agent.preflight()
        results: list[KindResult] = []
        files: list[Path] = []
        for index, suite in enumerate(suites):
            if index:
                await self._clock.sleep(suite.policy.pause_between_cases_seconds)
            with self._journal.recording(suite.kind) as log_file:
                result = await self._evaluator.evaluate(suite)
                written = self._writer.write_kind(result)
            files.extend((*written, log_file))
            logger.info(
                f"[{suite.kind}] {result.status}: {result.count(Status.PASSED)}/{result.executed} "
                f"cases passed, {result.count(Status.SKIPPED)} skipped, report {written[-1]}"
            )
            results.append(result)
        overall = self._writer.write_overall(tuple(results))
        logger.info(f"Overall report: {overall}")
        return EvaluationOutcome(tuple(results), tuple(files), overall)
