from collections.abc import Sequence
from datetime import datetime

from agent_evaluation.application.case_player import CasePlayer
from agent_evaluation.application.kind_evaluator import KindEvaluator
from agent_evaluation.domain.capability import Capabilities, Capability
from agent_evaluation.domain.check.check import CheckContext
from agent_evaluation.domain.check.judge import Grade
from agent_evaluation.domain.exchange import Exchange
from agent_evaluation.domain.reply import AgentReply
from agent_evaluation.domain.rules import Markers, Rules, SecurityRules
from agent_evaluation.domain.run_policy import RunPolicy

STARTED: datetime = datetime(2026, 10, 20, 15, 30, 12)


class ScriptedAgent:
    def __init__(self, *replies: AgentReply | Exception) -> None:
        self._replies = list(replies)
        self.sent: list[tuple[str, str, bool]] = []
        self.preflights = 0

    async def preflight(self) -> None:
        self.preflights += 1

    async def send(self, message: str, conversation_id: str, auto_approve: bool) -> AgentReply:
        self.sent.append((message, conversation_id, auto_approve))
        reply = self._replies.pop(0) if len(self._replies) > 1 else self._replies[0]
        if isinstance(reply, Exception):
            raise reply
        return reply


class FixedJudge:
    def __init__(self, score: float = 1.0, reason: str = "looks right") -> None:
        self.score = score
        self.reason = reason
        self.calls: list[tuple[str, tuple[Exchange, ...]]] = []

    async def grade(self, criterion: str, transcript: Sequence[Exchange]) -> Grade:
        self.calls.append((criterion, tuple(transcript)))
        return Grade(self.score, self.reason)


class RecordingClock:
    def __init__(self) -> None:
        self.sleeps: list[float] = []
        self._ticks = 0.0

    def now(self) -> datetime:
        return STARTED

    def monotonic(self) -> float:
        self._ticks += 1.0
        return self._ticks

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)


def rules(**available: bool) -> Rules:
    defaults = {"python": True, "files_read": True, "jira": False, "guardrail": False}
    patterns = {
        "python": ("python_executor",),
        "files_read": ("file_reader",),
        "jira": ("*jira*",),
        "guardrail": (),
    }
    return Rules(
        capabilities=Capabilities(
            Capability(name, {**defaults, **available}[name], patterns[name]) for name in defaults
        ),
        markers=Markers(plan_status="Formulating a plan", tool_status_prefix="Running "),
        security=SecurityRules(
            instruction_markers=("Pick the FIRST intent",),
            secret_patterns=(r"nvapi-[A-Za-z0-9_-]{20,}",),
        ),
        pass_score=0.7,
    )


def policy(**changes: float | int | None) -> RunPolicy:
    values: dict = {
        "runs": 2,
        "pause_between_runs_seconds": 5.0,
        "pause_between_messages_seconds": 1.0,
        "pause_between_cases_seconds": 10.0,
        "retry_on_error": 1,
        "retry_pause_seconds": 30.0,
        "case_pass_rate": 0.5,
    }
    return RunPolicy(**{**values, **changes})


def reply(content: str = "Paris", outcome: str = "answered", **fields) -> AgentReply:
    return AgentReply(content=content, outcome=outcome, seconds=2.0, **fields)


def context(answer: AgentReply, judge: FixedJudge | None = None, **available: bool) -> CheckContext:
    exchange = Exchange("main", "a question", False, answer)
    return CheckContext(
        exchange, (exchange,), rules(**available), judge or FixedJudge(), "ab12cd34"
    )


def evaluator(agent: ScriptedAgent, clock: RecordingClock, judge: FixedJudge | None = None):
    current = rules()
    return KindEvaluator(CasePlayer(agent, judge or FixedJudge(), clock, current), clock, current)
