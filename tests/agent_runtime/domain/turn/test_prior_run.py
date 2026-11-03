from agent_runtime.domain.turn.action import Action
from agent_runtime.domain.turn.prior_run import KEPT_ACTIONS, PriorRun


def _calls(count: int, start: int = 0) -> list[Action]:
    return [Action("echo", f"n={n}", True, str(n)) for n in range(start, start + count)]


def test_a_run_keeps_every_tool_call_up_to_the_limit() -> None:
    run = PriorRun(0).followed_by(2, _calls(3))

    assert run == PriorRun(2, tuple(_calls(3)))


def test_a_long_run_keeps_only_its_last_tool_calls_and_counts_the_others() -> None:
    run = PriorRun(0).followed_by(1, _calls(KEPT_ACTIONS + 5))

    assert run.actions == tuple(_calls(KEPT_ACTIONS, start=5))
    assert run.earlier == 5


def test_each_pause_adds_to_the_count_of_tool_calls_not_kept() -> None:
    first = PriorRun(0).followed_by(1, _calls(KEPT_ACTIONS + 5))

    second = first.followed_by(1, _calls(10, start=KEPT_ACTIONS + 5))

    assert second.earlier == 15
    assert second.actions[-1] == _calls(1, start=KEPT_ACTIONS + 14)[0]
    assert len(second.actions) == KEPT_ACTIONS


def test_the_calls_not_kept_are_mentioned_before_the_ones_kept() -> None:
    lines = PriorRun(1, tuple(_calls(1)), earlier=7).render_actions()

    assert lines == ["(7 earlier tool calls, not shown)", "echo(n=0): ok -> 0"]
    assert PriorRun(1, tuple(_calls(1))).render_actions() == ["echo(n=0): ok -> 0"]
