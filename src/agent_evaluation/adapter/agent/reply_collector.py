from typing import Any

from agent_evaluation.adapter.agent.sse_stream import SseEvent
from agent_evaluation.domain.exception import AgentUnavailable
from agent_evaluation.domain.reply import AgentReply


class ReplyCollector:
    def __init__(self) -> None:
        self._statuses: list[str] = []
        self._errors: list[str] = []
        self._tokens: int = 0
        self._final: dict[str, Any] | None = None

    @property
    def tokens(self) -> int:
        return self._tokens

    def add(self, event: SseEvent) -> None:
        content = str(event.data.get("content") or "")
        match event.name:
            case "status":
                self._statuses.append(content)
            case "token":
                self._tokens += 1
            case "final":
                self._final = event.data
                if event.data.get("error"):
                    self._errors.append(str(event.data["error"]))
            case "error":
                self._errors.append(content)

    def reply(self, seconds: float) -> AgentReply:
        if self._final is None:
            reason = self._errors[0][:500] if self._errors else "no final event"
            raise AgentUnavailable(f"the agent stream ended without an answer: {reason}")
        metadata = {
            str(key): str(value) for key, value in (self._final.get("metadata") or {}).items()
        }
        return AgentReply(
            content=str(self._final.get("content") or ""),
            outcome=metadata.get("outcome", ""),
            tools=_listed(metadata.get("tools", "")),
            statuses=tuple(self._statuses),
            errors=tuple(self._errors),
            model=metadata.get("model", ""),
            input_tokens=_number(metadata.get("input_tokens")),
            output_tokens=_number(metadata.get("output_tokens")),
            iterations=_number(metadata.get("iteration")),
            seconds=seconds,
            metadata=metadata,
        )


def _listed(text: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in text.split(",") if item.strip())


def _number(value: str | None) -> int:
    try:
        return int(float(value)) if value else 0
    except ValueError:
        return 0
