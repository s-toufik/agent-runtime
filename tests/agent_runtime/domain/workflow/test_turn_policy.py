import pytest

from agent_runtime.domain.turn.draft import Draft
from agent_runtime.domain.turn.intent import Intent
from agent_runtime.domain.turn.turn import Turn
from agent_runtime.domain.workflow.conditions import always
from agent_runtime.domain.workflow.step import Step
from agent_runtime.domain.workflow.turn_policy import TurnPolicy
from agent_runtime.domain.workflow.turn_shape import TurnShape
from tests.agent_runtime.domain.builders import (
    PLAN,
    accept,
    answer,
    calling,
    failure,
    result,
    retry,
    turn,
)

POLICY = TurnPolicy()


@pytest.mark.parametrize(
    ("intent", "expected"),
    [
        (Intent.TASK, Step.PLAN),
        (Intent.PLAN_REVISION, Step.PLAN),
        (None, Step.PLAN),
        (Intent.AMBIGUOUS, Step.CLARIFY),
        (Intent.DIRECT, Step.ACT),
        (Intent.REWORK, Step.ACT),
        (Intent.PLAN_APPROVAL, Step.ACT),
    ],
)
def test_after_understanding_the_intent_picks_the_route(
    intent: Intent | None, expected: Step
) -> None:
    assert POLICY.next(Step.UNDERSTAND, turn(intent)) == expected


@pytest.mark.parametrize("done", [Step.PLAN, Step.CLARIFY])
def test_a_plan_or_a_question_ends_the_work(done: Step) -> None:
    assert POLICY.next(done, turn(Intent.TASK)) == Step.FINISH


def _acted(current: Turn, *work) -> Turn:
    for item in work:
        if hasattr(item, "tool_calls"):
            current.drafted(item)
        else:
            current.observed([item])
    return current


def test_tool_calls_are_run_while_steps_remain() -> None:
    current = _acted(turn(Intent.PLAN_APPROVAL, plan=PLAN), calling("echo"))

    assert POLICY.next(Step.ACT, current) == Step.RUN_TOOLS


def test_tool_calls_after_the_last_step_end_the_turn() -> None:
    current = _acted(
        turn(Intent.PLAN_APPROVAL, max_steps=2), calling("echo"), result(), calling("echo")
    )

    assert POLICY.next(Step.ACT, current) == Step.FINISH


def test_a_plain_direct_answer_is_not_reviewed() -> None:
    assert POLICY.next(Step.ACT, _acted(turn(Intent.DIRECT), answer())) == Step.FINISH


@pytest.mark.parametrize(
    "current",
    [
        _acted(turn(Intent.REWORK), answer()),
        _acted(turn(Intent.DIRECT), calling("echo"), result(), answer()),
        _acted(turn(Intent.PLAN_APPROVAL, plan=PLAN), calling("echo"), result(), answer()),
    ],
)
def test_any_other_answer_is_reviewed(current: Turn) -> None:
    assert POLICY.next(Step.ACT, current) == Step.REVIEW


@pytest.mark.parametrize("done", [Step.RUN_TOOLS, Step.FEEDBACK])
def test_tools_and_feedback_lead_back_to_acting(done: Step) -> None:
    assert POLICY.next(done, turn()) == Step.ACT


def _reviewed(verdict, retries: int = 0, steps: int = 1, max_steps: int = 5) -> Turn:
    current = turn(Intent.REWORK, max_steps=max_steps)
    for _ in range(steps):
        current.drafted(answer())
    for _ in range(retries):
        current.give_feedback("fix it")
    current.reviewed(verdict)
    return current


@pytest.mark.parametrize(
    ("current", "expected"),
    [
        (_reviewed(retry()), Step.FEEDBACK),
        (_reviewed(accept()), Step.FINISH),
        (_reviewed(retry(), retries=2), Step.FINISH),
        (_reviewed(retry(), steps=5), Step.FINISH),
    ],
)
def test_a_rejected_answer_is_retried_only_within_both_limits(
    current: Turn, expected: Step
) -> None:
    assert POLICY.next(Step.REVIEW, current) == expected


def test_a_finished_turn_is_summarized_then_ends() -> None:
    assert POLICY.next(Step.FINISH, turn()) == Step.SUMMARIZE
    assert POLICY.next(Step.SUMMARIZE, turn()) == Step.END


def test_an_actor_asking_for_a_plan_gets_one_when_the_turn_has_none() -> None:
    current = _acted(turn(Intent.DIRECT), Draft.asking_for_plan("read the report"))

    assert POLICY.next(Step.ACT, current) == Step.PLAN


@pytest.mark.parametrize("draft", [answer("Step 1: done."), Draft.asking_for_plan("more")])
def test_an_answer_before_the_plan_is_done_goes_back_to_work(draft: Draft) -> None:
    current = _acted(turn(Intent.PLAN_APPROVAL, plan=PLAN), draft)

    assert POLICY.next(Step.ACT, current) == Step.ACT


def test_a_failed_step_is_still_open() -> None:
    current = _acted(turn(Intent.PLAN_APPROVAL, plan=PLAN), calling("echo"), failure(), answer())

    assert POLICY.next(Step.ACT, current) == Step.ACT


def test_an_unfinished_plan_out_of_steps_ends_the_turn() -> None:
    current = _acted(turn(Intent.PLAN_APPROVAL, max_steps=2, plan=PLAN), answer(), answer())

    assert POLICY.next(Step.ACT, current) == Step.FINISH


VALID_SHAPES = [
    TurnShape(direct, clarify, plan, review)
    for direct in (True, False)
    for clarify in (True, False)
    for plan in (True, False)
    for review in (True, False)
    if direct or plan
]


@pytest.mark.parametrize("screen", [False, True], ids=["no_screen", "screen"])
@pytest.mark.parametrize("shape", VALID_SHAPES, ids=lambda shape: "-".join(shape.routes))
def test_every_step_a_shape_reaches_always_has_a_way_out(shape: TurnShape, screen: bool) -> None:
    policy = TurnPolicy(shape, screen=screen)

    for step in policy.steps():
        rows = [row for row in policy.TRANSITIONS if row.source is step]
        assert rows, f"{step} has no way out"
        assert rows[-1].when is always, f"{step} can get stuck: its last row has a condition"
    assert Step.FINISH in policy.steps()


def test_the_orchestrator_shape_plans_what_others_answer_directly() -> None:
    policy = TurnPolicy(TurnShape(direct=False, clarify=True, plan=True, review=True))

    assert policy.next(Step.UNDERSTAND, turn(Intent.DIRECT)) == Step.PLAN
    assert policy.next(Step.UNDERSTAND, turn(Intent.REWORK)) == Step.PLAN
    assert policy.next(Step.UNDERSTAND, turn(Intent.AMBIGUOUS)) == Step.CLARIFY
    assert policy.next(Step.UNDERSTAND, turn(Intent.PLAN_APPROVAL)) == Step.ACT


def test_without_clarify_an_ambiguous_message_takes_the_best_reading() -> None:
    answering = TurnPolicy(TurnShape(direct=True, clarify=False, plan=True, review=True))
    planning = TurnPolicy(TurnShape(direct=False, clarify=False, plan=True, review=True))

    assert answering.next(Step.UNDERSTAND, turn(Intent.AMBIGUOUS)) == Step.ACT
    assert planning.next(Step.UNDERSTAND, turn(Intent.AMBIGUOUS)) == Step.PLAN
    assert Step.CLARIFY not in answering.steps()


def test_the_chat_shape_answers_a_task_directly_and_never_plans() -> None:
    policy = TurnPolicy(TurnShape(direct=True, clarify=True, plan=False, review=True))

    assert policy.next(Step.UNDERSTAND, turn(Intent.TASK)) == Step.ACT
    assert policy.next(Step.ACT, _answered(Intent.TASK)) == Step.REVIEW
    assert Step.PLAN not in policy.steps()
    assert Step.RUN_TOOLS not in policy.steps()


def test_without_review_an_answer_is_final() -> None:
    policy = TurnPolicy(TurnShape(direct=True, clarify=True, plan=True, review=False))

    assert policy.next(Step.ACT, _answered(Intent.TASK)) == Step.FINISH
    assert Step.REVIEW not in policy.steps()
    assert Step.FEEDBACK not in policy.steps()


def test_the_full_shape_reaches_every_step_but_screen() -> None:
    assert set(TurnPolicy().steps()) == set(Step) - {Step.END, Step.SCREEN}
    assert Step.SCREEN in TurnPolicy(screen=True).steps()


def _answered(intent: Intent) -> Turn:
    answered = turn(intent)
    answered.drafted(answer())
    return answered
