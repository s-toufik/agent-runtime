import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SseEvent:
    name: str
    data: dict[str, Any]


async def sse_events(lines: AsyncIterator[str]) -> AsyncIterator[SseEvent]:
    name, data = "message", []
    async for line in lines:
        if not line:
            if data:
                yield SseEvent(name, _decoded("\n".join(data)))
            name, data = "message", []
        elif line.startswith("event:"):
            name = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data.append(line.removeprefix("data:").lstrip())
    if data:
        yield SseEvent(name, _decoded("\n".join(data)))


def _decoded(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {"content": text}
    return value if isinstance(value, dict) else {"content": value}
