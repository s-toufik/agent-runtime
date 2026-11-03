from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlannedStep:
    action: str
    tool: str | None = None

    def render(self) -> str:
        return f"{self.action} (tool: {self.tool or 'none'})"


@dataclass(frozen=True, slots=True)
class Plan:
    task: str
    steps: tuple[PlannedStep, ...]
    expected_result: str = ""

    @property
    def uses_tools(self) -> bool:
        return any(step.tool for step in self.steps)

    def render(self) -> str:
        steps = (f"{n}. {step.render()}" for n, step in enumerate(self.steps, 1))
        return "\n".join(["### Plan", *steps, *self.render_expected_result()])

    def render_expected_result(self) -> list[str]:
        return ["### Expected result", self.expected_result] if self.expected_result else []
