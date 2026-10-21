from dataclasses import dataclass
from enum import StrEnum


class GuardDecision(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class Screening:
    decision: GuardDecision
    reason: str = ""

    @property
    def blocks(self) -> bool:
        return self.decision is GuardDecision.BLOCK

    @classmethod
    def allow(cls) -> Screening:
        return cls(GuardDecision.ALLOW)

    @classmethod
    def block(cls, reason: str) -> Screening:
        return cls(GuardDecision.BLOCK, reason)
