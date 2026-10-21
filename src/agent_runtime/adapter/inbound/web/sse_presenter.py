from agent_runtime.adapter.inbound.web.schema.agent_message_schema import AgentMessageSchema
from agent_runtime.adapter.inbound.web.schema.agent_message_stream_schema import (
    AgentMessageStreamSchema,
)
from agent_runtime.adapter.inbound.web.schema.message_stream_type import MessageStreamType
from agent_runtime.domain.event.turn_event import TurnEvent, TurnEventKind
from agent_runtime.domain.turn.answer import Answer
from agent_runtime.domain.turn.outcome import Outcome
from agent_runtime.domain.turn.token_usage import TokenUsage
from agent_runtime.domain.workflow.step import Step

STEP_STATUS: dict[Step, str] = {
    Step.UNDERSTAND: "Comprehending the request",
    Step.PLAN: "Formulating a plan",
    Step.REVIEW: "Reviewing the answer",
}
APPROVAL_PROMPT: str = (
    "Reply **yes** to approve the plan, **Drop plan** to cancel, or specify any required changes."
)


class SsePresenter:
    def present(self, event: TurnEvent, session_id: str) -> list[bytes]:
        match event.kind:
            case TurnEventKind.STEP_STARTED:
                status = self._status(event)
                return [_stream(MessageStreamType.STATUS, status)] if status else []
            case TurnEventKind.ANSWER_DELTA:
                return [_stream(MessageStreamType.TOKEN, event.text)]
            case TurnEventKind.FINISHED:
                return self._finished(event, session_id)
            case TurnEventKind.FAILED:
                return [_stream(MessageStreamType.ERROR, event.error)]

    @staticmethod
    def complete() -> bytes:
        return _stream(MessageStreamType.COMPLETE, "")

    @staticmethod
    def error(trace: str) -> bytes:
        return _stream(MessageStreamType.ERROR, trace)

    @staticmethod
    def _status(event: TurnEvent) -> str | None:
        if event.step is Step.RUN_TOOLS:
            return f"Running {', '.join(event.tools)}"
        return STEP_STATUS.get(event.step) if event.step else None

    @staticmethod
    def _finished(event: TurnEvent, session_id: str) -> list[bytes]:
        answer = event.answer
        final = AgentMessageSchema(
            session_id=session_id,
            content=_content(answer) if answer else "",
            metadata=_metadata(event),
        ).serialize()
        return [final]


def _metadata(event: TurnEvent) -> dict[str, str]:
    answer: Answer | None = event.answer
    usage: TokenUsage | None = event.usage
    fields: dict[str, str] = {}
    if event.duration_ms > 0:
        fields["elapsed_time"] = _format_duration(event.duration_ms)
    if usage is not None and usage.input_tokens > 0:
        fields["input_tokens"] = str(usage.input_tokens)
    if usage is not None and usage.output_tokens > 0:
        fields["output_tokens"] = str(usage.output_tokens)
    if event.model:
        fields["model"] = event.model
    if answer is not None:
        fields["outcome"] = str(answer.outcome)
    if event.tools:
        fields["tools"] = ", ".join(event.tools)

    fields["iteration"] = str(event.steps_taken)
    fields["max_iteration"] = str(event.max_steps)
    return fields


def _format_duration(duration_ms: int) -> str:
    seconds = max(0, duration_ms) // 1000
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _content(answer: Answer) -> str:
    if answer.outcome is Outcome.AWAITING_APPROVAL:
        return f"{answer.text}\n\n---\n{APPROVAL_PROMPT}"
    return answer.text


def _stream(event_type: MessageStreamType, content: str) -> bytes:
    return AgentMessageStreamSchema(type=event_type, content=content).serialize()
