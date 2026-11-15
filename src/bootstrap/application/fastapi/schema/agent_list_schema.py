from pydantic import BaseModel

from agent_runtime.domain.agent.peer_agent import PeerAgent


class AgentSkillSchema(BaseModel):
    id: str
    name: str
    description: str
    tags: list[str]
    examples: list[str]


class AgentSchema(BaseModel):
    name: str
    description: str
    skills: list[AgentSkillSchema]


class AgentListSchema(BaseModel):
    agents: list[AgentSchema]

    @classmethod
    def from_domain(cls, agents: tuple[PeerAgent, ...]) -> AgentListSchema:
        return cls(
            agents=[
                AgentSchema(
                    name=agent.name,
                    description=agent.description,
                    skills=[
                        AgentSkillSchema(
                            id=skill.id,
                            name=skill.name,
                            description=skill.description,
                            tags=list(skill.tags),
                            examples=list(skill.examples),
                        )
                        for skill in agent.skills
                    ],
                )
                for agent in agents
            ]
        )
