from dataclasses import dataclass

from agent_evaluation.domain.capability import Capabilities


@dataclass(frozen=True, slots=True)
class Markers:
    plan_status: str
    tool_status_prefix: str


@dataclass(frozen=True, slots=True)
class SecurityRules:
    instruction_markers: tuple[str, ...] = ()
    secret_patterns: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Rules:
    capabilities: Capabilities
    markers: Markers
    security: SecurityRules
    pass_score: float
