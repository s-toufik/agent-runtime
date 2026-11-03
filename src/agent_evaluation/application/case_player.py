import logging
import uuid

from agent_evaluation.application.port.agent import Agent
from agent_evaluation.application.port.clock import Clock
from agent_evaluation.domain.case import Case, Say
from agent_evaluation.domain.check.check import RUN_ID, Check, CheckContext, CheckResult
from agent_evaluation.domain.check.judge import Judge
from agent_evaluation.domain.check.reply_checks import Completes
from agent_evaluation.domain.exchange import Exchange
from agent_evaluation.domain.kind import Kind
from agent_evaluation.domain.result import ExchangeResult, RunResult, Status
from agent_evaluation.domain.rules import Rules
from agent_evaluation.domain.run_policy import RunPolicy

logger: logging.Logger = logging.getLogger(__name__)

ALWAYS: tuple[Check, ...] = (Completes(),)


class CasePlayer:
    def __init__(self, agent: Agent, judge: Judge, clock: Clock, rules: Rules) -> None:
        self._agent = agent
        self._judge = judge
        self._clock = clock
        self._rules = rules

    async def play(
        self, kind: Kind, case: Case, number: int, attempt: int, policy: RunPolicy
    ) -> RunResult:
        run_id: str = uuid.uuid4().hex[:8]
        started_at, started = self._clock.now(), self._clock.monotonic()
        conversations: dict[str, str] = {}
        results: list[ExchangeResult] = []
        logger.debug(f"=== {case.id} run {number} attempt {attempt} (run_id {run_id}) ===")

        for index, say in enumerate(case.says):
            if index:
                await self._clock.sleep(policy.pause_between_messages_seconds)
            conversation_id = conversations.setdefault(
                say.conversation, f"eval-{kind.lower()}-{case.id}-{run_id}-{say.conversation}"
            )
            exchange = await self._exchange(say, conversation_id, run_id, index, len(case.says))
            history = tuple(
                result.exchange
                for result in results
                if result.exchange.conversation == say.conversation
            )
            context = CheckContext(exchange, (*history, exchange), self._rules, self._judge, run_id)
            results.append(ExchangeResult(exchange, await self._verify(say, context)))

        status = Status.PASSED if all(result.passed for result in results) else Status.FAILED
        seconds = self._clock.monotonic() - started
        return RunResult(number, status, run_id, started_at, seconds, attempt, tuple(results))

    async def _exchange(
        self, say: Say, conversation_id: str, run_id: str, index: int, total: int
    ) -> Exchange:
        message = say.message.replace(RUN_ID, run_id)
        logger.debug(
            f"--- message {index + 1}/{total} to {conversation_id} "
            f"(auto_approve={say.auto_approve}):\n{message}"
        )
        reply = await self._agent.send(message, conversation_id, say.auto_approve)
        logger.debug(
            f"--- reply in {reply.seconds:.1f}s, outcome {reply.outcome or 'none'}, "
            f"tools [{', '.join(reply.tools)}], tokens {reply.input_tokens}/{reply.output_tokens}:"
            f"\n{reply.content}"
        )
        return Exchange(say.conversation, message, say.auto_approve, reply)

    @staticmethod
    async def _verify(say: Say, context: CheckContext) -> tuple[CheckResult, ...]:
        results: list[CheckResult] = []
        for check in (*ALWAYS, *say.expect):
            result = await check.verify(context)
            mark = "PASS" if result.passed else "FAIL"
            score = f" [{result.score:.2f}]" if result.score is not None else ""
            logger.debug(f"    {mark}{score} {result.label}: {result.detail}".rstrip(": "))
            results.append(result)
        return tuple(results)
