from collections.abc import AsyncIterator
from typing import TypedDict

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph

from agent_runtime.adapter.outbound.langgraph.graph.agent_graph_builder import (
    AgentGraphBuilder,
)
from agent_runtime.adapter.outbound.langgraph.graph.policy_router import PolicyRouter
from agent_runtime.adapter.outbound.langgraph.langgraph_event_publisher import (
    LangGraphEventPublisher,
)
from agent_runtime.adapter.outbound.langgraph.langgraph_workflow_runner import (
    LangGraphWorkflowRunner,
)
from agent_runtime.adapter.outbound.langgraph.node.agent_nodes import agent_nodes
from agent_runtime.adapter.outbound.langgraph.state.turn_state_codec import TurnStateCodec
from agent_runtime.application.step.act_step import ActStep
from agent_runtime.application.step.clarify_step import ClarifyStep
from agent_runtime.application.step.feedback_step import FeedbackStep
from agent_runtime.application.step.finish_step import FinishStep
from agent_runtime.application.step.plan_step import PlanStep
from agent_runtime.application.step.review_step import ReviewStep
from agent_runtime.application.step.run_tools_step import RunToolsStep
from agent_runtime.application.step.step_handler import StepHandler
from agent_runtime.application.step.summarize_step import SummarizeStep
from agent_runtime.application.step.understand_step import UnderstandStep
from agent_runtime.domain.conversation.conversation import Conversation
from agent_runtime.domain.conversation.message import Speaker
from agent_runtime.domain.event.turn_event import TurnEvent, TurnEventKind
from agent_runtime.domain.tool.tool_call import ToolCall
from agent_runtime.domain.turn.action import Action
from agent_runtime.domain.turn.answer import NO_PLAN
from agent_runtime.domain.turn.draft import Draft
from agent_runtime.domain.turn.intent import Intent
from agent_runtime.domain.turn.outcome import Outcome
from agent_runtime.domain.turn.plan import PlannedStep
from agent_runtime.domain.turn.turn import Turn
from agent_runtime.domain.turn.turn_options import TurnOptions
from agent_runtime.domain.turn.turn_settings import TurnSettings
from agent_runtime.domain.turn.understanding import Understanding
from agent_runtime.domain.workflow.step import Step
from agent_runtime.domain.workflow.turn_policy import TurnPolicy
from tests.agent_runtime.application.fakes import (
    ECHO,
    EchoExecutor,
    FakeActor,
    FakeCatalog,
    FakeClassifier,
    FakePlanner,
    FakeReviewer,
    FakeSummarizer,
    FakeTokens,
    InMemoryWorkflowRunner,
)
from tests.agent_runtime.domain.builders import accept, retry

CONVERSATION = "c1"
ECHO_HI = (PlannedStep("echo hi", "echo"),)


class Agent:
    def __init__(
        self,
        runner_kind: str,
        logger,
        understandings: list[Understanding] | None = None,
        plans: list[tuple[PlannedStep, ...] | None] | None = None,
        drafts: list[Draft] | None = None,
        verdicts: list | None = None,
    ) -> None:
        self.classifier = FakeClassifier(*(understandings or []))
        self.planner = FakePlanner(*(plans or []))
        self.actor = FakeActor(*(drafts or []))
        self.reviewer = FakeReviewer(*(verdicts or []))
        self.executor = EchoExecutor()
        catalog = FakeCatalog(ECHO)
        self.steps = steps = [
            UnderstandStep(self.classifier, logger),
            PlanStep(self.planner, catalog),
            ClarifyStep(),
            ActStep(self.actor, catalog),
            RunToolsStep(self.executor),
            ReviewStep(self.reviewer, logger),
            FeedbackStep(logger),
            FinishStep(),
            SummarizeStep(FakeSummarizer(), FakeTokens(0), logger),
        ]
        policy = TurnPolicy()
        self.runner = (
            InMemoryWorkflowRunner(steps, policy)
            if runner_kind == "memory"
            else _langgraph(steps, logger, InMemorySaver())
        )
        self.events: list[TurnEvent] = []

    async def say(
        self, message: str, settings: TurnSettings | None = None, auto_approve: bool = False
    ) -> TurnEvent:
        turn = Turn(
            message,
            "m",
            settings or TurnSettings(max_steps=6),
            options=TurnOptions(auto_approve=auto_approve),
        )
        self.events = [event async for event in self._run(turn)]
        return self.events[-1]

    async def _run(self, turn: Turn) -> AsyncIterator[TurnEvent]:
        async for event in self.runner.run(CONVERSATION, turn):
            yield event

    async def stored(self) -> Conversation:
        if isinstance(self.runner, InMemoryWorkflowRunner):
            return self.runner.conversations[CONVERSATION]
        snapshot = await self.runner.graph.aget_state({"configurable": {"thread_id": CONVERSATION}})
        stored = TurnStateCodec().stored_conversation(snapshot.values)
        assert stored is not None
        return stored

    def entered(self) -> list[Step | None]:
        return [e.step for e in self.events if e.kind is TurnEventKind.STEP_STARTED]


RUNNERS = pytest.mark.parametrize("runner_kind", ["memory", "langgraph"])


def _langgraph(steps: list[StepHandler], logger, checkpointer) -> LangGraphWorkflowRunner:
    codec, policy = TurnStateCodec(), TurnPolicy()
    builder = AgentGraphBuilder(
        agent_nodes(steps, codec, LangGraphEventPublisher()), policy, PolicyRouter(policy, codec)
    )
    return LangGraphWorkflowRunner(builder.build(checkpointer), logger)


def _understood(intent: Intent, query: str = "the query", **fields) -> Understanding:
    return Understanding(intent=intent, query=query, **fields)


def _calls(*names: str) -> Draft:
    return Draft("", tuple(ToolCall(f"call_{i}", n, {"text": "hi"}) for i, n in enumerate(names)))


@RUNNERS
async def test_a_task_is_planned_approved_then_executed_with_tools(runner_kind, logger) -> None:
    agent = Agent(
        runner_kind,
        logger,
        understandings=[
            _understood(Intent.TASK, "say hi"),
            _understood(Intent.PLAN_APPROVAL, "yes"),
        ],
        plans=[ECHO_HI],
        drafts=[_calls("echo"), Draft("echo said hi")],
        verdicts=[accept()],
    )

    proposal = await agent.say("say hi")

    assert proposal.answer is not None
    assert proposal.answer.outcome is Outcome.AWAITING_APPROVAL
    assert "1. echo hi (tool: echo)" in proposal.answer.text
    assert agent.entered() == [Step.UNDERSTAND, Step.PLAN, Step.FINISH, Step.SUMMARIZE]

    answer = await agent.say("yes")

    assert answer.answer is not None
    assert (answer.answer.text, answer.answer.outcome) == ("echo said hi", Outcome.ANSWERED)
    assert (answer.steps_taken, answer.max_steps) == (2, 6)
    assert agent.entered() == [
        Step.UNDERSTAND,
        Step.ACT,
        Step.RUN_TOOLS,
        Step.ACT,
        Step.REVIEW,
        Step.FINISH,
        Step.SUMMARIZE,
    ]
    assert [e.tools for e in agent.events if e.step is Step.RUN_TOOLS] == [("echo",)]
    executed: Turn = agent.actor.calls[-1][1]
    assert executed.plan is not None and executed.query == "say hi"
    reviewed: Turn = agent.reviewer.calls[0][1]
    assert [result.output for result in reviewed.evidence] == ["echo:hi"]
    assert agent.classifier.calls[-1][0].pending_plan is not None
    stored = await agent.stored()
    assert [m.speaker for m in stored.messages] == [Speaker.USER, Speaker.ASSISTANT] * 2
    assert stored.pending_plan is None


@RUNNERS
async def test_a_follow_up_is_understood_against_the_conversation(runner_kind, logger) -> None:
    agent = Agent(
        runner_kind,
        logger,
        understandings=[
            _understood(Intent.DIRECT, "what is VaR"),
            _understood(Intent.REWORK, "explain VaR for AI agents"),
        ],
        drafts=[Draft("VaR is a loss quantile."), Draft("For agents, ...")],
        verdicts=[accept()],
    )

    first = await agent.say("what is VaR?")
    answer = await agent.say("I mean for agents")

    assert first.answer is not None and first.answer.outcome is Outcome.ANSWERED
    assert answer.answer is not None and answer.answer.text == "For agents, ..."
    assert len(agent.reviewer.calls) == 1
    history = agent.classifier.calls[-1][0].messages
    assert [m.text for m in history] == ["what is VaR?", "VaR is a loss quantile."]


@RUNNERS
async def test_a_rejected_draft_is_retried_and_only_the_last_one_is_kept(
    runner_kind, logger
) -> None:
    agent = Agent(
        runner_kind,
        logger,
        understandings=[_understood(Intent.REWORK, "hi")],
        drafts=[Draft("first try"), Draft("second try")],
        verdicts=[retry("too short"), accept()],
    )

    answer = await agent.say("hi")

    assert answer.answer is not None and answer.answer.text == "second try"
    assert agent.entered().count(Step.REVIEW) == 2
    retried: Turn = agent.actor.calls[-1][1]
    assert retried.work[-1].critique == "too short"
    stored = await agent.stored()
    assert [m.text for m in stored.messages] == ["hi", "second try"]


@RUNNERS
async def test_an_ambiguous_message_gets_a_clarifying_question(runner_kind, logger) -> None:
    agent = Agent(
        runner_kind,
        logger,
        understandings=[_understood(Intent.AMBIGUOUS, "?", clarification_question="Which desk?")],
    )

    answer = await agent.say("the numbers")

    assert answer.answer is not None
    assert (answer.answer.text, answer.answer.outcome) == ("Which desk?", Outcome.CLARIFICATION)
    assert agent.actor.calls == []


@RUNNERS
async def test_running_out_of_steps_after_every_step_ran_pauses_the_plan(
    runner_kind, logger
) -> None:
    agent = Agent(
        runner_kind,
        logger,
        understandings=[_understood(Intent.TASK, "loop"), _understood(Intent.PLAN_APPROVAL, "yes")],
        plans=[ECHO_HI],
        drafts=[_calls("echo"), _calls("echo")],
    )

    await agent.say("loop")
    answer = await agent.say("yes", TurnSettings(max_steps=2))

    assert answer.answer is not None
    assert answer.answer.outcome is Outcome.BUDGET_EXHAUSTED and answer.answer.resumable
    assert "✓ 1. echo hi" in answer.answer.text
    assert (answer.steps_taken, answer.max_steps) == (2, 2)
    assert agent.reviewer.calls == []
    stored = await agent.stored()
    assert stored.pending is not None and stored.pending.is_paused


@RUNNERS
async def test_continue_carries_on_a_plan_cut_off_after_every_step_ran(runner_kind, logger) -> None:
    agent = Agent(
        runner_kind,
        logger,
        understandings=[
            _understood(Intent.TASK, "say hi until done"),
            _understood(Intent.PLAN_APPROVAL),
            _understood(Intent.PLAN_APPROVAL, "continue"),
        ],
        plans=[ECHO_HI],
        drafts=[_calls("echo"), _calls("echo"), _calls("echo"), Draft("Said hi twice.")],
        verdicts=[accept()],
    )
    await agent.say("say hi until done")
    await agent.say("yes", TurnSettings(max_steps=2))

    answer = await agent.say("continue")

    assert answer.answer is not None
    assert (answer.answer.text, answer.answer.outcome) == ("Said hi twice.", Outcome.ANSWERED)
    assert len(agent.planner.calls) == 1
    assert [call.name for call in agent.executor.calls] == ["echo", "echo"]
    resumed: Turn = agent.actor.calls[2][1]
    assert resumed.prior is not None and resumed.prior.done == len(ECHO_HI)
    assert [action.tool for action in resumed.prior.actions] == ["echo"]
    assert (await agent.stored()).pending is None


async def test_a_thread_stored_in_an_older_format_starts_a_new_conversation(logger) -> None:
    saver = InMemorySaver()
    old = StateGraph(_OldState)  # ty: ignore[invalid-argument-type]
    old.add_node("ingest", lambda state: {"state": {"transcript": ["older layout"]}})
    old.set_entry_point("ingest")
    old.add_edge("ingest", END)
    config = {"configurable": {"thread_id": CONVERSATION}}
    await old.compile(checkpointer=saver).ainvoke({"state": {}}, config)
    agent = Agent("langgraph", logger, [_understood(Intent.DIRECT, "hello")], drafts=[Draft("hi")])
    agent.runner = _langgraph(agent.steps, logger, saver)

    answer = await agent.say("hello")

    assert answer.answer is not None and answer.answer.text == "hi"
    assert agent.classifier.calls[0][0].messages == []


class _OldState(TypedDict):
    state: dict


def test_an_unreadable_stored_conversation_is_ignored() -> None:
    codec = TurnStateCodec()

    assert codec.stored_conversation({}) is None
    assert codec.stored_conversation({"conversation": {"transcript": []}}) is None


def test_a_conversation_stored_before_plans_could_pause_still_loads() -> None:
    stored = {
        "id": CONVERSATION,
        "messages": [{"speaker": "user", "text": "hi"}],
        "summary": "",
        "pending_plan": {"task": "t", "steps": [{"action": "a", "tool": "echo"}]},
        "actions": [],
    }

    conversation = TurnStateCodec().stored_conversation({"conversation": stored})

    assert conversation is not None and [m.text for m in conversation.messages] == ["hi"]
    assert conversation.pending is None


@RUNNERS
async def test_a_request_misread_as_direct_gets_a_plan_in_the_same_turn(
    runner_kind, logger
) -> None:
    agent = Agent(
        runner_kind,
        logger,
        understandings=[
            _understood(Intent.DIRECT, "explain change.md"),
            _understood(Intent.PLAN_APPROVAL, "yes"),
        ],
        plans=[(PlannedStep("read change.md", "echo"),)],
        drafts=[
            Draft.asking_for_plan("read change.md"),
            _calls("echo"),
            Draft("It lists changes."),
        ],
        verdicts=[accept()],
    )

    proposal = await agent.say("explain change.md")

    assert proposal.answer is not None
    assert proposal.answer.outcome is Outcome.AWAITING_APPROVAL
    assert agent.entered() == [Step.UNDERSTAND, Step.ACT, Step.PLAN, Step.FINISH, Step.SUMMARIZE]
    assert (await agent.stored()).pending_plan is not None

    answer = await agent.say("yes")

    assert answer.answer is not None and answer.answer.text == "It lists changes."
    assert agent.executor.calls[0].name == "echo"


@RUNNERS
async def test_with_auto_approve_a_task_is_planned_and_carried_out_in_one_turn(
    runner_kind, logger
) -> None:
    agent = Agent(
        runner_kind,
        logger,
        understandings=[_understood(Intent.TASK, "say hi")],
        plans=[ECHO_HI],
        drafts=[_calls("echo"), Draft("echo said hi")],
        verdicts=[accept()],
    )

    answer = await agent.say("say hi", auto_approve=True)

    assert answer.answer is not None
    assert (answer.answer.text, answer.answer.outcome) == ("echo said hi", Outcome.ANSWERED)
    assert agent.entered() == [
        Step.UNDERSTAND,
        Step.PLAN,
        Step.ACT,
        Step.RUN_TOOLS,
        Step.ACT,
        Step.REVIEW,
        Step.FINISH,
        Step.SUMMARIZE,
    ]
    assert (await agent.stored()).pending_plan is None


@RUNNERS
async def test_with_auto_approve_a_request_misread_as_direct_still_ends_with_the_tool_result(
    runner_kind, logger
) -> None:
    agent = Agent(
        runner_kind,
        logger,
        understandings=[_understood(Intent.DIRECT, "explain change.md")],
        plans=[(PlannedStep("read change.md", "echo"),)],
        drafts=[
            Draft.asking_for_plan("read change.md"),
            _calls("echo"),
            Draft("It lists changes."),
        ],
        verdicts=[accept()],
    )

    answer = await agent.say("explain change.md", auto_approve=True)

    assert answer.answer is not None and answer.answer.text == "It lists changes."
    assert agent.executor.calls[0].name == "echo"
    executed: Turn = agent.actor.calls[1][1]
    assert executed.plan is not None and executed.work == []


@RUNNERS
async def test_a_step_described_instead_of_run_is_asked_for_again(runner_kind, logger) -> None:
    agent = Agent(
        runner_kind,
        logger,
        understandings=[_understood(Intent.TASK, "report"), _understood(Intent.PLAN_APPROVAL)],
        plans=[(PlannedStep("compute", "echo"), PlannedStep("write the report", "file_writer"))],
        drafts=[
            _calls("echo"),
            Draft("Step 2: I wrote the report."),
            _calls("file_writer"),
            Draft("The report is in report.md."),
        ],
        verdicts=[accept()],
    )

    await agent.say("report")
    answer = await agent.say("yes")

    assert answer.answer is not None and answer.answer.text == "The report is in report.md."
    assert [call.name for call in agent.executor.calls] == ["echo", "file_writer"]
    assert agent.entered() == [
        Step.UNDERSTAND,
        Step.ACT,
        Step.RUN_TOOLS,
        Step.ACT,
        Step.ACT,
        Step.RUN_TOOLS,
        Step.ACT,
        Step.REVIEW,
        Step.FINISH,
        Step.SUMMARIZE,
    ]
    reviewed: Turn = agent.reviewer.calls[0][1]
    assert [action.tool for action in reviewed.actions] == ["echo", "file_writer"]


@RUNNERS
async def test_a_plan_left_unfinished_is_reported_honestly(runner_kind, logger) -> None:
    agent = Agent(
        runner_kind,
        logger,
        understandings=[_understood(Intent.TASK, "report"), _understood(Intent.PLAN_APPROVAL)],
        plans=[(PlannedStep("compute", "echo"), PlannedStep("write the report", "file_writer"))],
        drafts=[_calls("echo"), Draft("I combined it and wrote it back."), Draft("Done!")],
    )

    await agent.say("report")
    answer = await agent.say("yes", TurnSettings(max_steps=3))

    assert answer.answer is not None
    assert answer.answer.outcome is Outcome.BUDGET_EXHAUSTED
    assert "✓ 1. compute" in answer.answer.text
    assert "→ 2. write the report" in answer.answer.text
    assert "wrote it back" not in answer.answer.text
    assert agent.reviewer.calls == []


@RUNNERS
async def test_the_next_turn_knows_which_tools_ran_before(runner_kind, logger) -> None:
    agent = Agent(
        runner_kind,
        logger,
        understandings=[_understood(Intent.TASK, "say hi"), _understood(Intent.TASK, "again")],
        plans=[ECHO_HI, ECHO_HI],
        drafts=[_calls("echo"), Draft("echo said hi")],
        verdicts=[accept()],
    )

    await agent.say("say hi", auto_approve=True)
    await agent.say("again")

    replanned: Conversation = agent.planner.calls[-1][0]
    assert replanned.actions == [Action("echo", "text='hi'", True, "echo:hi")]
    assert (await agent.stored()).actions == replanned.actions


@RUNNERS
async def test_a_plan_that_cannot_be_written_ends_the_turn_plainly(runner_kind, logger) -> None:
    agent = Agent(runner_kind, logger, understandings=[_understood(Intent.TASK, "x")], plans=[None])

    answer = await agent.say("x")

    assert answer.answer is not None
    assert (answer.answer.text, answer.answer.outcome) == (NO_PLAN, Outcome.BEST_EFFORT)
    assert (await agent.stored()).pending_plan is None


REPORT_STEPS = (PlannedStep("compute", "echo"), PlannedStep("write the report", "file_writer"))


async def _paused_after_the_first_step(agent: Agent) -> TurnEvent:
    await agent.say("report")
    return await agent.say("yes", TurnSettings(max_steps=2))


@RUNNERS
async def test_continue_resumes_a_paused_plan_where_it_stopped(runner_kind, logger) -> None:
    agent = Agent(
        runner_kind,
        logger,
        understandings=[
            _understood(Intent.TASK, "report"),
            _understood(Intent.PLAN_APPROVAL),
            _understood(Intent.PLAN_APPROVAL, "continue"),
        ],
        plans=[REPORT_STEPS],
        drafts=[
            _calls("echo"),
            Draft("I combined it."),
            _calls("file_writer"),
            Draft("The report is in report.md."),
        ],
        verdicts=[accept()],
    )
    paused = await _paused_after_the_first_step(agent)
    assert paused.answer is not None and paused.answer.resumable

    answer = await agent.say("continue")

    assert answer.answer is not None
    assert (answer.answer.text, answer.answer.outcome) == (
        "The report is in report.md.",
        Outcome.ANSWERED,
    )
    assert agent.entered() == [
        Step.UNDERSTAND,
        Step.ACT,
        Step.RUN_TOOLS,
        Step.ACT,
        Step.REVIEW,
        Step.FINISH,
        Step.SUMMARIZE,
    ]
    assert len(agent.planner.calls) == 1
    assert [call.name for call in agent.executor.calls] == ["echo", "file_writer"]
    asked: Conversation = agent.classifier.calls[-1][0]
    assert asked.pending is not None and asked.pending.is_paused
    resumed: Turn = agent.actor.calls[2][1]
    assert resumed.query == "report" and resumed.prior is not None
    assert [action.tool for action in resumed.prior.actions] == ["echo"]
    reviewed: Turn = agent.reviewer.calls[0][1]
    assert reviewed.prior is not None
    assert [action.tool for action in (*reviewed.prior.actions, *reviewed.actions)] == [
        "echo",
        "file_writer",
    ]
    assert (await agent.stored()).pending is None


@RUNNERS
async def test_a_resumed_run_that_is_interrupted_leaves_the_plan_paused(
    runner_kind, logger
) -> None:
    agent = Agent(
        runner_kind,
        logger,
        understandings=[
            _understood(Intent.TASK, "report"),
            _understood(Intent.PLAN_APPROVAL),
            _understood(Intent.PLAN_APPROVAL, "continue"),
            _understood(Intent.PLAN_APPROVAL, "continue"),
        ],
        plans=[REPORT_STEPS],
        drafts=[
            _calls("echo"),
            Draft("I combined it."),
            RuntimeError("the model server is down"),
            _calls("file_writer"),
            Draft("The report is in report.md."),
        ],
        verdicts=[accept()],
    )
    await _paused_after_the_first_step(agent)

    with pytest.raises(RuntimeError):
        await agent.say("continue")
    interrupted = (await agent.stored()).pending
    assert interrupted is not None and interrupted.prior is not None
    assert interrupted.prior.done == 1

    answer = await agent.say("continue")

    assert answer.answer is not None
    assert answer.answer.text == "The report is in report.md."
    assert (await agent.stored()).pending is None


@RUNNERS
async def test_narrowing_a_paused_plan_replans_only_what_is_left(runner_kind, logger) -> None:
    agent = Agent(
        runner_kind,
        logger,
        understandings=[
            _understood(Intent.TASK, "report"),
            _understood(Intent.PLAN_APPROVAL),
            _understood(Intent.PLAN_REVISION, "just write the report"),
        ],
        plans=[REPORT_STEPS, (PlannedStep("write the report", "file_writer"),)],
        drafts=[_calls("echo"), Draft("I combined it.")],
    )
    await _paused_after_the_first_step(agent)

    proposal = await agent.say("just write the report")

    assert proposal.answer is not None
    assert proposal.answer.outcome is Outcome.AWAITING_APPROVAL
    revised: Conversation = agent.planner.calls[-1][0]
    assert revised.pending is not None and revised.pending.is_paused
    stored = await agent.stored()
    assert stored.pending is not None and not stored.pending.is_paused


@RUNNERS
async def test_a_new_task_drops_a_paused_plan(runner_kind, logger) -> None:
    agent = Agent(
        runner_kind,
        logger,
        understandings=[
            _understood(Intent.TASK, "report"),
            _understood(Intent.PLAN_APPROVAL),
            _understood(Intent.DIRECT, "what is VaR"),
        ],
        plans=[REPORT_STEPS],
        drafts=[_calls("echo"), Draft("I combined it."), Draft("A loss quantile.")],
    )
    await _paused_after_the_first_step(agent)

    await agent.say("what is VaR?")

    assert (await agent.stored()).pending is None
