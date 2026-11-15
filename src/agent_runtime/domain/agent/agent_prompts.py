from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from agent_runtime.domain.workflow.step import Step

PROMPTED_STEPS: tuple[Step, ...] = (
    Step.UNDERSTAND,
    Step.PLAN,
    Step.ACT,
    Step.REVIEW,
    Step.SCREEN,
    Step.SUMMARIZE,
)


@dataclass(frozen=True, slots=True)
class AgentPrompts:
    by_step: Mapping[Step, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for step, text in self.by_step.items():
            if step not in PROMPTED_STEPS:
                raise ValueError(f"step {step.value!r} has no system prompt")
            if not text.strip():
                raise ValueError(f"the system prompt of step {step.value!r} is empty")
        object.__setattr__(self, "by_step", MappingProxyType(dict(self.by_step)))

    def for_step(self, step: Step) -> str | None:
        return self.by_step.get(step)
