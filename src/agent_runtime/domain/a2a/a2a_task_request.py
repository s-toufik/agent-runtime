from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class A2aTaskRequest:
    text: str
    context_id: str
    model_name: str = ""
    auto_approve: bool = False
