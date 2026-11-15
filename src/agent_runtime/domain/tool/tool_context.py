from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolContext:
    conversation: str
    model: str
