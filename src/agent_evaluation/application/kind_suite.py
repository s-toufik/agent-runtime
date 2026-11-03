from dataclasses import dataclass, field

from agent_evaluation.domain.capability import Capabilities
from agent_evaluation.domain.case import Case
from agent_evaluation.domain.kind import Kind
from agent_evaluation.domain.run_policy import RunPolicy


@dataclass(frozen=True, slots=True)
class KindSuite:
    kind: Kind
    cases: tuple[Case, ...]
    policy: RunPolicy
    skipped_ids: frozenset[str] = field(default_factory=frozenset)

    def skip_reason(self, case: Case, capabilities: Capabilities) -> str | None:
        if case.id in self.skipped_ids:
            return "skipped in the control panel"
        missing = capabilities.unavailable(case.requires)
        if missing:
            return f"needs {', '.join(missing)} (not available)"
        present = capabilities.available(case.unless)
        if present:
            return f"only runs while {', '.join(present)} is not available"
        return None
