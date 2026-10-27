import pytest

from agent_runtime.domain.conversation.conversation import Conversation
from agent_runtime.domain.conversation.message import Message, Speaker
from agent_runtime.domain.turn.action import Action
from agent_runtime.domain.turn.answer import Answer
from agent_runtime.domain.turn.intent import Intent
from agent_runtime.domain.turn.pending_plan import PendingPlan
from agent_runtime.domain.turn.prior_run import PriorRun
from agent_runtime.domain.turn.turn_options import TurnOptions
from agent_runtime.domain.turn.understanding import Understanding
from tests.agent_runtime.domain.builders import (
    PLAN,
    REPORT,
    calling,
    result,
    stopped_after_the_count,
    turn,
)


def _waiting() -> Conversation:
    conversation = Conversation(id="c1")
    conversation.propose(PLAN)
    return conversation


def test_approving_takes_the_pending_plan_into_the_turn() -> None:
    conversation, current = _waiting(), turn(None)

    conversation.interpret(current, Understanding(Intent.PLAN_APPROVAL, "yes"))

    assert current.plan == PLAN
    assert current.query == PLAN.task
    assert conversation.pending_plan is None


@pytest.mark.parametrize("intent", [Intent.PLAN_REVISION, Intent.AMBIGUOUS])
def test_discussing_the_plan_keeps_it_pending(intent: Intent) -> None:
    conversation, current = _waiting(), turn(None)

    conversation.interpret(current, Understanding(intent, "q", clarification_question="?"))

    assert conversation.pending_plan == PLAN
    assert current.plan is None


@pytest.mark.parametrize("intent", [Intent.TASK, Intent.DIRECT, Intent.REWORK])
def test_moving_on_drops_the_pending_plan(intent: Intent) -> None:
    conversation, current = _waiting(), turn(None)

    conversation.interpret(current, Understanding(intent, "q"))

    assert conversation.pending_plan is None


def test_an_approval_with_nothing_pending_is_read_as_direct() -> None:
    conversation, current = Conversation(id="c1"), turn(None)

    conversation.interpret(current, Understanding(Intent.PLAN_APPROVAL, "yes"))

    assert current.intent is Intent.DIRECT
    assert current.plan is None


def test_closing_a_turn_keeps_the_message_and_its_answer() -> None:
    conversation, current = Conversation(id="c1"), turn()
    current.finish(Answer.answered("hello back"))

    conversation.close(current)

    assert conversation.messages == [
        Message(Speaker.USER, "msg"),
        Message(Speaker.ASSISTANT, "hello back"),
    ]


def test_closing_a_turn_logs_the_tools_it_ran_and_keeps_only_the_latest() -> None:
    old = [Action("echo", "", True, str(i)) for i in range(20)]
    conversation, current = Conversation(id="c1", actions=list(old)), turn(plan=PLAN)
    current.drafted(calling("echo"))
    current.observed([result(output="new")])
    current.finish(Answer.answered("done"))

    conversation.close(current)

    assert conversation.actions == [*old[1:], Action("echo", "", True, "new")]


def test_compacting_keeps_only_the_last_messages_and_the_summary() -> None:
    messages = [Message(Speaker.USER, str(i)) for i in range(6)]
    conversation = Conversation(id="c1", messages=list(messages))

    assert conversation.older_than(4) == messages[:2]
    conversation.compact("earlier: 0, 1", keep_last=4)

    assert conversation.summary == "earlier: 0, 1"
    assert conversation.messages == messages[2:]


def test_a_submitted_plan_waits_for_the_user_by_default() -> None:
    conversation, current = Conversation(id="c1"), turn(Intent.TASK)

    conversation.submit(current, PLAN)

    assert conversation.pending_plan == PLAN
    assert current.plan is None
    assert current.answer == Answer.approval_request(PLAN)


def test_with_auto_approve_a_submitted_plan_is_carried_out_at_once() -> None:
    conversation, current = Conversation(id="c1"), turn(Intent.TASK)
    current.options = TurnOptions(auto_approve=True)

    conversation.submit(current, PLAN)

    assert conversation.pending_plan is None
    assert current.plan == PLAN
    assert current.answer is None


def _paused() -> Conversation:
    conversation = Conversation(id="c1")
    conversation.pause(stopped_after_the_count())
    return conversation


def test_pausing_keeps_the_plan_pending_with_how_far_it_got() -> None:
    conversation = _paused()

    assert conversation.pending is not None and conversation.pending.is_paused
    assert conversation.pending_plan == REPORT
    assert conversation.pending.prior == PriorRun(1, (Action("echo", "", True, "ok"),))


def test_approving_a_paused_plan_resumes_it_where_it_stopped() -> None:
    conversation, current = _paused(), turn(None)

    conversation.interpret(current, Understanding(Intent.PLAN_APPROVAL, "continue"))

    assert current.plan == REPORT and current.query == REPORT.task
    assert current.progress is not None and current.progress.current == REPORT.steps[1]
    assert conversation.pending is None


def test_revising_a_paused_plan_keeps_it_paused_for_the_planner() -> None:
    conversation, current = _paused(), turn(None)
    paused = conversation.pending

    conversation.interpret(current, Understanding(Intent.PLAN_REVISION, "only the count"))

    assert conversation.pending == paused


@pytest.mark.parametrize("intent", [Intent.TASK, Intent.PLAN_REJECTION, Intent.REWORK])
def test_moving_on_or_rejecting_drops_a_paused_plan(intent: Intent) -> None:
    conversation, current = _paused(), turn(None)

    conversation.interpret(current, Understanding(intent, "q"))

    assert conversation.pending is None


def test_a_proposed_plan_is_pending_but_not_paused() -> None:
    conversation = Conversation(id="c1")

    conversation.propose(PLAN)

    assert conversation.pending == PendingPlan(PLAN)
