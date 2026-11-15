import pytest

from agent_runtime.domain.agent.agent import Agent
from agent_runtime.domain.agent.agent_prompts import AgentPrompts
from agent_runtime.domain.agent.agent_routes import AgentRoutes
from agent_runtime.domain.agent.tool_scope import ToolScope
from agent_runtime.domain.workflow.step import Step


def test_an_agent_has_every_route_all_tools_and_the_default_paths_by_default() -> None:
    agent = Agent("chat", "the conversation agent")

    assert agent.tool_scope == ToolScope("all")
    assert agent.turns.direct and agent.turns.plan and agent.turns.review and agent.turns.clarify
    assert (agent.routes.a2a, agent.routes.api2a) == ("/a2a", "/v1/api2a")
    assert agent.peers == ()


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"name": "Chat"}, "lower case"),
        ({"description": " "}, "needs a description"),
        ({"peers": ("chat",)}, "its own peer"),
        ({"peers": ("analysis", "analysis")}, "a peer twice"),
    ],
)
def test_an_agent_that_cannot_work_is_refused(values, message) -> None:
    with pytest.raises(ValueError, match=message):
        Agent(**({"name": "chat", "description": "the conversation agent"} | values))


@pytest.mark.parametrize("name", ["", "Obs", "obs ervation", "-x"])
def test_a_tool_scope_is_a_lower_case_name(name) -> None:
    with pytest.raises(ValueError, match="tool scope"):
        ToolScope(name)


def test_none_skips_the_toolbox_and_all_takes_every_tool() -> None:
    assert ToolScope("none").uses_toolbox is False
    assert ToolScope("all").is_all and ToolScope("all").uses_toolbox
    assert not ToolScope("observation").is_all


@pytest.mark.parametrize(
    ("a2a", "api2a"),
    [("a2a", "/v1/api2a"), ("/a2a/", "/v1/api2a"), ("/same", "/same"), ("/a//b", "/x")],
)
def test_routes_are_absolute_distinct_paths(a2a, api2a) -> None:
    with pytest.raises(ValueError, match="route"):
        AgentRoutes(a2a, api2a)


def test_a_prompt_is_found_by_its_step_and_is_read_only() -> None:
    prompts = AgentPrompts({Step.ACT: "You are {identity}. {mode}"})

    assert prompts.for_step(Step.ACT) == "You are {identity}. {mode}"
    assert prompts.for_step(Step.PLAN) is None
    with pytest.raises(TypeError):
        prompts.by_step[Step.PLAN] = "x"  # ty: ignore[invalid-assignment]


@pytest.mark.parametrize(
    ("by_step", "message"),
    [({Step.FINISH: "x"}, "has no system prompt"), ({Step.ACT: "  "}, "is empty")],
)
def test_a_prompt_for_a_step_without_one_or_an_empty_prompt_is_refused(by_step, message) -> None:
    with pytest.raises(ValueError, match=message):
        AgentPrompts(by_step)
