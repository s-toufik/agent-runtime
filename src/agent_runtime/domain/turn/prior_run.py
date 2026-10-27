from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from agent_runtime.domain.turn.action import Action

KEPT_ACTIONS: int = 20


@dataclass(frozen=True, slots=True)
class PriorRun:
    done: int
    actions: tuple[Action, ...] = field(default_factory=tuple)
    earlier: int = 0

    def followed_by(self, done: int, actions: Sequence[Action]) -> PriorRun:
        every = (*self.actions, *actions)
        kept = every[-KEPT_ACTIONS:]
        return PriorRun(done, kept, self.earlier + len(every) - len(kept))

    def render_actions(self) -> list[str]:
        earlier = [f"({self.earlier} earlier tool calls, not shown)"] if self.earlier else []
        return [*earlier, *(action.render() for action in self.actions)]
