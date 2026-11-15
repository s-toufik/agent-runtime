from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AgentSkill:
    id: str
    name: str
    description: str
    tags: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
