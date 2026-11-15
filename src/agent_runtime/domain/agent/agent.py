import re
from dataclasses import dataclass, field

from agent_runtime.domain.agent.agent_prompts import AgentPrompts
from agent_runtime.domain.agent.agent_routes import AgentRoutes
from agent_runtime.domain.agent.agent_skill import AgentSkill
from agent_runtime.domain.agent.tool_scope import ToolScope
from agent_runtime.domain.workflow.turn_shape import TurnShape

_NAME = re.compile(r"^[a-z][a-z0-9-]*$")


@dataclass(frozen=True, slots=True)
class Agent:
    name: str
    description: str
    skills: tuple[AgentSkill, ...] = ()
    tool_scope: ToolScope = field(default_factory=ToolScope)
    turns: TurnShape = field(default_factory=TurnShape)
    peers: tuple[str, ...] = ()
    routes: AgentRoutes = field(default_factory=AgentRoutes)
    prompts: AgentPrompts = field(default_factory=AgentPrompts)

    def __post_init__(self) -> None:
        if not _NAME.match(self.name):
            raise ValueError(f"agent name {self.name!r} must be lower case letters, digits or '-'")
        if not self.description.strip():
            raise ValueError(f"agent {self.name!r} needs a description")
        if self.name in self.peers:
            raise ValueError(f"agent {self.name!r} cannot be its own peer")
        if len(set(self.peers)) != len(self.peers):
            raise ValueError(f"agent {self.name!r} lists a peer twice")
