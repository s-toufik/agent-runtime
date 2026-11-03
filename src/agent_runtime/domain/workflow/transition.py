from dataclasses import dataclass

from agent_runtime.domain.workflow.conditions import Condition, always
from agent_runtime.domain.workflow.step import Step


@dataclass(frozen=True, slots=True)
class Transition:
    source: Step
    target: Step
    when: Condition = always
