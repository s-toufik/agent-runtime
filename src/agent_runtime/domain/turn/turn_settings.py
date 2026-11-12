from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TurnSettings:
    max_steps: int = 10
    max_retries: int = 2
    context_tokens: int = 8000
    output_tokens: int = 1024
