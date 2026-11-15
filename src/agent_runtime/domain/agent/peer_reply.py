from dataclasses import dataclass
from enum import StrEnum


class PeerOutcome(StrEnum):
    ANSWERED = "answered"
    NEEDS_INPUT = "needs_input"
    REFUSED = "refused"
    FAILED = "failed"
    UNREACHABLE = "unreachable"


@dataclass(frozen=True, slots=True)
class PeerRequest:
    agent: str
    message: str


@dataclass(frozen=True, slots=True)
class PeerReply:
    agent: str
    outcome: PeerOutcome
    text: str

    def render(self) -> str:
        return f"## {self.agent} ({self.outcome.value})\n{self.text.strip() or '(no text)'}"
