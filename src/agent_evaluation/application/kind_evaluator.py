import logging

from agent_evaluation.application.case_player import CasePlayer
from agent_evaluation.application.kind_suite import KindSuite
from agent_evaluation.application.port.clock import Clock
from agent_evaluation.domain.case import Case
from agent_evaluation.domain.exception import AgentUnavailable, JudgeUnavailable
from agent_evaluation.domain.kind import Kind
from agent_evaluation.domain.result import CaseResult, KindResult, RunResult, Status
from agent_evaluation.domain.rules import Rules
from agent_evaluation.domain.run_policy import RunPolicy

logger: logging.Logger = logging.getLogger(__name__)


class KindEvaluator:
    def __init__(self, player: CasePlayer, clock: Clock, rules: Rules) -> None:
        self._player = player
        self._clock = clock
        self._rules = rules

    async def evaluate(self, suite: KindSuite) -> KindResult:
        started_at = self._clock.now()
        results: list[CaseResult] = []
        played = 0
        total = len(suite.cases)

        for index, case in enumerate(suite.cases, 1):
            reason = suite.skip_reason(case, self._rules.capabilities)
            if reason is not None:
                logger.info(f"[{suite.kind}] ({index}/{total}) {case.id}: SKIPPED, {reason}")
                results.append(CaseResult.skipped(case, reason))
                continue
            if played:
                await self._clock.sleep(suite.policy.pause_between_cases_seconds)
            played += 1
            results.append(await self._case(suite.kind, case, suite.policy, f"({index}/{total})"))

        return KindResult(suite.kind, suite.policy, tuple(results), started_at, self._clock.now())

    async def _case(self, kind: Kind, case: Case, base: RunPolicy, position: str) -> CaseResult:
        policy = base.for_case(case)
        logger.info(f"[{kind}] {position} {case.id}: {case.title}")
        runs: list[RunResult] = []
        for number in range(1, policy.runs + 1):
            if number > 1:
                await self._clock.sleep(policy.pause_between_runs_seconds)
            run = await self._run(kind, case, number, policy)
            logger.info(
                f"[{kind}]     run {number}/{policy.runs}: {run.status} ({run.seconds:.1f}s)"
                + (f", {run.error}" if run.error else "")
            )
            runs.append(run)
        result = CaseResult.from_runs(case, tuple(runs), policy.case_pass_rate)
        flaky = ", flaky" if result.is_flaky else ""
        logger.info(
            f"[{kind}]     => {result.status} ({result.passed_runs}/{len(runs)} runs){flaky}"
        )
        return result

    async def _run(self, kind: Kind, case: Case, number: int, policy: RunPolicy) -> RunResult:
        attempts = policy.retry_on_error + 1
        error = ""
        started_at, started = self._clock.now(), self._clock.monotonic()
        for attempt in range(1, attempts + 1):
            try:
                return await self._player.play(kind, case, number, attempt, policy)
            except (AgentUnavailable, JudgeUnavailable) as exception:
                error = f"{type(exception).__name__}: {exception}"
                logger.warning(f"[{kind}]     attempt {attempt}/{attempts} errored: {error}")
                if attempt < attempts:
                    await self._clock.sleep(policy.retry_pause_seconds)
        seconds = self._clock.monotonic() - started
        return RunResult(number, Status.ERROR, "", started_at, seconds, attempts, error=error)
