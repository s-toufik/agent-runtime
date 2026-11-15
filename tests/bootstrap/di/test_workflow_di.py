from dataclasses import replace
from pathlib import Path

import pytest

from agent_runtime.adapter.outbound.llm.enum.answer_delivery import AnswerDelivery
from agent_runtime.adapter.outbound.llm.langchain.reply.streamed_reply import StreamedReply
from agent_runtime.adapter.outbound.llm.langchain.reply.whole_reply import WholeReply
from agent_runtime.adapter.outbound.tool.toolbox import Toolbox
from agent_runtime.application.tool.tool_registry import ToolRegistry
from agent_runtime.domain.workflow.step import Step
from bootstrap.di.agent_di import AgentDI
from tests.bootstrap.di.conftest import make_settings

REAL_AGENTS = Path(__file__).resolve().parents[3] / "agents"


@pytest.mark.parametrize("guardrail_enabled", [False, True], ids=["no_screen", "screen"])
async def test_the_workflow_graph_has_one_node_per_step(guardrail_enabled: bool) -> None:
    di = AgentDI(make_settings(guardrail_enabled=guardrail_enabled))
    toolbox = Toolbox(ToolRegistry([]), di._logging)

    runner = di._workflow.runner(toolbox, checkpointer=None)

    nodes = set(runner.graph.get_graph().nodes) - {"__start__", "__end__"}
    expected = {step.value for step in Step if step is not Step.END}
    assert nodes == (expected if guardrail_enabled else expected - {Step.SCREEN.value})
    await di._models.close()


@pytest.mark.parametrize(
    ("delivery", "reader"),
    [(AnswerDelivery.STREAM, StreamedReply), (AnswerDelivery.WHOLE, WholeReply)],
)
async def test_the_final_reply_follows_the_answer_delivery(monkeypatch, delivery, reader) -> None:
    monkeypatch.setenv("AGENT_ANSWER_DELIVERY", delivery)
    di = AgentDI(make_settings())

    assert isinstance(di._workflow.final_reply(), reader)
    await di._models.close()


@pytest.mark.parametrize(
    ("agent", "absent"),
    [
        ("chat", {Step.PLAN, Step.RUN_TOOLS, Step.SCREEN}),
        ("orchestration", {Step.SCREEN}),
    ],
)
async def test_an_agent_s_graph_has_only_the_steps_its_turns_reach(agent, absent) -> None:
    settings = replace(make_settings(), agent=agent, agents_directory=REAL_AGENTS)
    di = AgentDI(settings)

    runner = di._workflow.runner(Toolbox(ToolRegistry([]), di._logging), checkpointer=None)

    nodes = set(runner.graph.get_graph().nodes) - {"__start__", "__end__"}
    assert nodes == {step.value for step in Step if step is not Step.END} - {
        s.value for s in absent
    }
    await di._models.close()
