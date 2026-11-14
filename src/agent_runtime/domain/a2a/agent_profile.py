from dataclasses import dataclass, field

HOMELAB_DESCRIPTION: str = (
    "A homelab assistant that answers questions and carries out tasks with the tools "
    "its toolbox publishes (files, Python, Grafana, MongoDB, PostgreSQL)."
)


@dataclass(frozen=True, slots=True)
class AgentSkill:
    id: str
    name: str
    description: str
    tags: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()


HOMELAB_ASSISTANT: AgentSkill = AgentSkill(
    id="homelab-assistant",
    name="Homelab assistant",
    description=(
        "Answers directly when no tool is needed. A task that needs tools first returns a plan "
        'and waits for input: reply "yes" in the same task to run it, or say what to change. '
        'A plan stopped by the step limit also waits: reply "continue".'
    ),
    tags=("homelab", "observability", "databases", "python"),
    examples=(
        "Which pods restarted in the last hour?",
        "How many documents does each MongoDB database hold?",
    ),
)


@dataclass(frozen=True, slots=True)
class AgentProfile:
    name: str
    version: str
    description: str = HOMELAB_DESCRIPTION
    skills: tuple[AgentSkill, ...] = field(default=(HOMELAB_ASSISTANT,))
