from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class AgentReply:
    content: str
    outcome: str = ""
    tools: tuple[str, ...] = ()
    statuses: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    iterations: int = 0
    seconds: float = 0.0
    metadata: dict[str, str] = field(default_factory=dict)
