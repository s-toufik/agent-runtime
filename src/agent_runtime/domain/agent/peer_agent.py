from dataclasses import dataclass

from agent_runtime.domain.agent.agent_skill import AgentSkill


@dataclass(frozen=True, slots=True)
class PeerAgent:
    name: str
    description: str
    skills: tuple[AgentSkill, ...] = ()

    def render(self) -> str:
        skills = "; ".join(f"{skill.name}: {skill.description}" for skill in self.skills)
        return f"{self.name}: {self.description}" + (f" ({skills})" if skills else "")
