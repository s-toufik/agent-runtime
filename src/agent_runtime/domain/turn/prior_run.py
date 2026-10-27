from __future__ import annotations

from dataclasses import dataclass, field

from agent_runtime.domain.turn.action import Action


@dataclass(frozen=True, slots=True)
class PriorRun:
    done: int
    actions: tuple[Action, ...] = field(default_factory=tuple)
