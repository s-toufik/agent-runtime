from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_runtime.adapter.outbound.llm.langchain.prompts.generic_prompts import prompt_book
from agent_runtime.domain.agent.tool_scope import ToolScope
from agent_runtime.domain.workflow.step import Step
from agent_runtime.domain.workflow.turn_shape import TurnShape
from bootstrap.configuration.agent_definition import LoadAgentDefinition

AGENTS = Path(__file__).resolve().parents[3] / "agents"
NAMES = sorted(path.parent.name for path in AGENTS.glob("*/agent.yml"))


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def agent_yml(name: str = "chat", **extra: str) -> str:
    lines = [
        "agent:",
        f"  name: {name}",
        "  description: the conversation agent",
        "  tool_scope: none",
        "  turns: [direct, review]",
        *(f"  {key}: {value}" for key, value in extra.items()),
    ]
    return "\n".join(lines) + "\n"


def test_the_repository_holds_the_eight_agents() -> None:
    assert NAMES == [
        "analysis",
        "chat",
        "coding",
        "kitchen",
        "observation",
        "orchestration",
        "security",
        "travel",
    ]


@pytest.mark.parametrize("name", NAMES)
def test_every_agent_folder_loads_and_its_prompts_fit_their_steps(name) -> None:
    agent = LoadAgentDefinition(AGENTS, name)()

    assert agent.name == name
    assert agent.skills
    prompt_book(agent.description, agent.prompts)


def test_the_orchestrator_never_answers_directly_and_knows_the_other_agents() -> None:
    orchestration = LoadAgentDefinition(AGENTS, "orchestration")()

    assert orchestration.turns.direct is False
    assert orchestration.tool_scope == ToolScope("none")
    assert set(orchestration.peers) == set(NAMES) - {"orchestration"}
    assert orchestration.prompts.for_step(Step.PLAN)


def test_a_folder_becomes_an_agent(tmp_path) -> None:
    write(tmp_path / "chat" / "agent.yml", agent_yml(routes="{a2a: /agents/chat/a2a}"))
    write(tmp_path / "chat" / "prompts" / "act.md", "You are {identity}. {mode}")

    agent = LoadAgentDefinition(tmp_path, "chat")()

    assert agent.turns == TurnShape(direct=True, clarify=False, plan=False, review=True)
    assert agent.routes.a2a == "/agents/chat/a2a"
    assert agent.routes.api2a == "/v1/api2a"
    assert agent.prompts.for_step(Step.ACT) == "You are {identity}. {mode}"


def test_skills_can_live_in_their_own_folder(tmp_path) -> None:
    write(tmp_path / "chat" / "agent.yml", agent_yml(skills="${skills}"))
    write(
        tmp_path / "chat" / "skills" / "answer.yml",
        "skills:\n  answer:\n    id: answer\n    name: Answer\n    description: Answers.\n",
    )

    agent = LoadAgentDefinition(tmp_path, "chat")()

    assert [skill.id for skill in agent.skills] == ["answer"]


def test_an_unknown_agent_names_the_known_ones(tmp_path) -> None:
    write(tmp_path / "chat" / "agent.yml", agent_yml())

    with pytest.raises(FileNotFoundError, match=r"No agent 'travel'.*known: chat"):
        LoadAgentDefinition(tmp_path, "travel")()


def test_a_folder_must_name_its_own_agent(tmp_path) -> None:
    write(tmp_path / "chat" / "agent.yml", agent_yml(name="travel"))

    with pytest.raises(ValueError, match="names the agent 'travel', not 'chat'"):
        LoadAgentDefinition(tmp_path, "chat")()


def test_an_unknown_key_is_refused(tmp_path) -> None:
    write(tmp_path / "chat" / "agent.yml", agent_yml(persona="friendly"))

    with pytest.raises(ValidationError, match="persona"):
        LoadAgentDefinition(tmp_path, "chat")()


def test_a_prompt_file_for_no_step_is_refused(tmp_path) -> None:
    write(tmp_path / "chat" / "agent.yml", agent_yml())
    write(tmp_path / "chat" / "prompts" / "answer.md", "Answer.")

    with pytest.raises(ValueError, match="answer.md names no step"):
        LoadAgentDefinition(tmp_path, "chat")()
