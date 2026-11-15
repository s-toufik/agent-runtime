from dataclasses import replace

import pytest

from agent_runtime.adapter.outbound.llm.enum.answer_delivery import AnswerDelivery
from agent_runtime.adapter.outbound.llm.langchain.reply.streamed_reply import StreamedReply
from agent_runtime.adapter.outbound.llm.langchain.reply.whole_reply import WholeReply
from agent_runtime.adapter.outbound.tool.toolbox import Toolbox
from agent_runtime.application.tool.tool_registry import ToolRegistry
from agent_runtime.domain.workflow.step import Step
from bootstrap.di.agent_di import AgentDI
from tests.bootstrap.di.conftest import make_settings
from tests.support.agents import GUARDED_TEST_AGENT, TEST_AGENT


@pytest.mark.parametrize(
    ("agent", "guardrail"),
    [(TEST_AGENT, False), (GUARDED_TEST_AGENT, True)],
    ids=["no_screen", "screen"],
)
async def test_the_workflow_graph_screens_plans_only_when_the_agent_has_its_guardrail(
    agent: str, guardrail: bool
) -> None:
    di = AgentDI(make_settings(agent))
    toolbox = Toolbox(ToolRegistry([]), di._logging)

    runner = di._workflow.runner(toolbox, checkpointer=None)

    nodes = set(runner.graph.get_graph().nodes) - {"__start__", "__end__"}
    expected = {step.value for step in Step if step is not Step.END}
    assert nodes == (expected if guardrail else expected - {Step.SCREEN.value})
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
    ("turns", "absent"),
    [
        ("[direct, clarify, review]", {Step.PLAN, Step.RUN_TOOLS, Step.SCREEN}),
        ("[direct, clarify, plan, review]", {Step.SCREEN}),
    ],
)
async def test_an_agent_s_graph_has_only_the_steps_its_turns_reach(tmp_path, turns, absent) -> None:
    folder = tmp_path / "talk"
    folder.mkdir()
    (folder / "agent.yml").write_text(
        "agent:\n  name: talk\n  description: a test agent\n  tool_scope: none\n  guardrail: false\n"
        f"  turns: {turns}\n  skills:\n    - {{id: talk, name: Talk, description: Talks.}}\n"
    )
    settings = replace(make_settings(), agent="talk", agents_directory=tmp_path)
    di = AgentDI(settings)

    runner = di._workflow.runner(Toolbox(ToolRegistry([]), di._logging), checkpointer=None)

    nodes = set(runner.graph.get_graph().nodes) - {"__start__", "__end__"}
    assert nodes == {step.value for step in Step if step is not Step.END} - {
        s.value for s in absent
    }
    await di._models.close()
