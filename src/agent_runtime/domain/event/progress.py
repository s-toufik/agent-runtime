import json
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any

from agent_runtime.domain.agent.peer_reply import PeerReply
from agent_runtime.domain.tool.tool_call import ToolCall
from agent_runtime.domain.tool.tool_result import ToolResult
from agent_runtime.domain.turn.plan_progress import PlanProgress

DETAIL_LIMIT: int = 160
PROGRESS_KEY: str = "progress"


class ProgressKind(StrEnum):
    PLAN = "plan"
    TOOL = "tool"
    AGENT = "agent"


class StepState(StrEnum):
    DONE = "done"
    CURRENT = "current"
    TO_DO = "todo"


class ToolState(StrEnum):
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


AGENT_WORKING: str = "working"


@dataclass(frozen=True, slots=True)
class PlanStepView:
    number: int
    action: str
    tool: str | None
    state: StepState


@dataclass(frozen=True, slots=True)
class Progress:
    kind: ProgressKind
    path: tuple[str, ...] = ()
    steps: tuple[PlanStepView, ...] = field(default_factory=tuple)
    call_id: str = ""
    name: str = ""
    state: str = ""
    detail: str = ""

    @classmethod
    def plan(cls, progress: PlanProgress) -> Progress:
        return cls(
            ProgressKind.PLAN,
            steps=tuple(
                PlanStepView(index + 1, step.action, step.tool, _step_state(index, progress))
                for index, step in enumerate(progress.plan.steps)
            ),
        )

    @classmethod
    def tool_started(cls, call: ToolCall) -> Progress:
        return cls(
            ProgressKind.TOOL,
            call_id=call.id,
            name=call.name,
            state=ToolState.RUNNING,
            detail=_short(json.dumps(call.arguments, ensure_ascii=False, default=str)),
        )

    @classmethod
    def tool_finished(cls, result: ToolResult) -> Progress:
        return cls(
            ProgressKind.TOOL,
            call_id=result.call_id,
            name=result.tool_name,
            state=ToolState.FAILED if result.error is not None else ToolState.DONE,
            detail=_short(result.error or ""),
        )

    @classmethod
    def agent_started(cls, agent: str, task: str) -> Progress:
        return cls(ProgressKind.AGENT, name=agent, state=AGENT_WORKING, detail=_short(task))

    @classmethod
    def agent_finished(cls, reply: PeerReply) -> Progress:
        return cls(ProgressKind.AGENT, name=reply.agent, state=reply.outcome.value)

    def under(self, agent: str) -> Progress:
        return replace(self, path=(agent, *self.path))

    def to_dict(self) -> dict[str, Any]:
        fields: dict[str, Any] = {"kind": self.kind.value, "path": list(self.path)}
        if self.steps:
            fields["steps"] = [
                {
                    "number": step.number,
                    "action": step.action,
                    "tool": step.tool,
                    "state": step.state.value,
                }
                for step in self.steps
            ]
        for key, value in (
            ("callId", self.call_id),
            ("name", self.name),
            ("state", self.state),
            ("detail", self.detail),
        ):
            if value:
                fields[key] = value
        return fields

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, fields: Any) -> Progress | None:
        if not isinstance(fields, dict):
            return None
        try:
            kind = ProgressKind(fields.get("kind"))
        except ValueError:
            return None
        path = fields.get("path") or []
        steps = fields.get("steps") or []
        return cls(
            kind,
            path=tuple(str(agent) for agent in path if isinstance(agent, str)),
            steps=tuple(
                PlanStepView(
                    int(step.get("number", index + 1)),
                    str(step.get("action", "")),
                    step.get("tool") if isinstance(step.get("tool"), str) else None,
                    _parse_step_state(step.get("state")),
                )
                for index, step in enumerate(steps)
                if isinstance(step, dict)
            ),
            call_id=str(fields.get("callId", "")),
            name=str(fields.get("name", "")),
            state=str(fields.get("state", "")),
            detail=str(fields.get("detail", "")),
        )

    @classmethod
    def from_json(cls, text: str) -> Progress | None:
        try:
            return cls.from_dict(json.loads(text))
        except ValueError, TypeError:
            return None


def _step_state(index: int, progress: PlanProgress) -> StepState:
    if index < progress.done:
        return StepState.DONE
    return StepState.CURRENT if index == progress.done else StepState.TO_DO


def _parse_step_state(value: Any) -> StepState:
    try:
        return StepState(value)
    except ValueError:
        return StepState.TO_DO


def _short(text: str) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= DETAIL_LIMIT else f"{flat[: DETAIL_LIMIT - 1]}…"
