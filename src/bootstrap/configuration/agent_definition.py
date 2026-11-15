from pathlib import Path

from pycraftcore.application_configuration.adapter import OmegaTreeReader
from pydantic import BaseModel, ConfigDict, Field

from agent_runtime.domain.agent.agent import Agent
from agent_runtime.domain.agent.agent_prompts import PROMPTED_STEPS, AgentPrompts
from agent_runtime.domain.agent.agent_routes import A2A_PATH, API2A_PATH, AgentRoutes
from agent_runtime.domain.agent.agent_skill import AgentSkill
from agent_runtime.domain.agent.tool_scope import ToolScope
from agent_runtime.domain.workflow.step import Step
from agent_runtime.domain.workflow.turn_shape import Route, TurnShape

ROOT_FILE: str = "agent.yml"
ROOT_KEY: str = "agent"
FOLDERS: tuple[str, ...] = ("skills",)
PROMPTS_FOLDER: str = "prompts"
PROMPT_EXTENSION: str = ".md"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentSkillSchema(_Strict):
    id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)

    def to_domain(self) -> AgentSkill:
        return AgentSkill(
            self.id, self.name, self.description, tuple(self.tags), tuple(self.examples)
        )


class AgentRoutesSchema(_Strict):
    a2a: str = A2A_PATH
    api2a: str = API2A_PATH


class AgentSchema(_Strict):
    name: str
    description: str
    skills: list[AgentSkillSchema] | dict[str, AgentSkillSchema] = Field(default_factory=list)
    tool_scope: str
    turns: list[Route]
    peers: list[str] = Field(default_factory=list)
    routes: AgentRoutesSchema = Field(default_factory=AgentRoutesSchema)

    def skill_list(self) -> list[AgentSkillSchema]:
        return list(self.skills.values()) if isinstance(self.skills, dict) else self.skills


class LoadAgentDefinition:
    def __init__(self, agents_directory: Path, name: str) -> None:
        self._agents_directory = agents_directory
        self._name = name

    def __call__(self) -> Agent:
        folder: Path = self._folder()
        tree = OmegaTreeReader(folder / ROOT_FILE, [folder / name for name in FOLDERS])
        schema = AgentSchema(**tree.read(ROOT_KEY))
        if schema.name != self._name:
            raise ValueError(
                f"{folder / ROOT_FILE} names the agent {schema.name!r}, not {self._name!r}"
            )
        return Agent(
            name=schema.name,
            description=schema.description,
            skills=tuple(skill.to_domain() for skill in schema.skill_list()),
            tool_scope=ToolScope(schema.tool_scope),
            turns=TurnShape.of(schema.turns),
            peers=tuple(schema.peers),
            routes=AgentRoutes(schema.routes.a2a, schema.routes.api2a),
            prompts=_prompts(folder / PROMPTS_FOLDER),
        )

    def _folder(self) -> Path:
        folder: Path = self._agents_directory / self._name
        if not (folder / ROOT_FILE).is_file():
            known = sorted(
                path.parent.name for path in self._agents_directory.glob(f"*/{ROOT_FILE}")
            )
            raise FileNotFoundError(
                f"No agent {self._name!r} in {self._agents_directory} (known: {', '.join(known) or 'none'})"
            )
        return folder


def _prompts(folder: Path) -> AgentPrompts:
    steps: dict[str, Step] = {step.value: step for step in PROMPTED_STEPS}
    prompts: dict[Step, str] = {}
    for file in sorted(folder.glob(f"*{PROMPT_EXTENSION}")):
        step: Step | None = steps.get(file.stem)
        if step is None:
            raise ValueError(
                f"{file} names no step with a system prompt (one of: {', '.join(steps)})"
            )
        prompts[step] = file.read_text(encoding="utf-8")
    return AgentPrompts(prompts)
