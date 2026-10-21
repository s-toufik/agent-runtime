from dataclasses import dataclass
from typing import Protocol

from agent_evaluation.domain.check.judge import Judge
from agent_evaluation.domain.exchange import Exchange
from agent_evaluation.domain.reply import AgentReply
from agent_evaluation.domain.rules import Rules

RUN_ID: str = "{run_id}"


@dataclass(frozen=True, slots=True)
class CheckResult:
    label: str
    passed: bool
    detail: str = ""
    score: float | None = None


@dataclass(frozen=True, slots=True)
class CheckContext:
    exchange: Exchange
    history: tuple[Exchange, ...]
    rules: Rules
    judge: Judge
    run_id: str

    @property
    def reply(self) -> AgentReply:
        return self.exchange.reply

    def render(self, text: str) -> str:
        return text.replace(RUN_ID, self.run_id)


class Check(Protocol):
    @property
    def label(self) -> str: ...

    async def verify(self, context: CheckContext) -> CheckResult: ...
