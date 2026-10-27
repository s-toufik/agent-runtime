from agent_runtime.domain.turn.action import Action
from agent_runtime.domain.turn.pending_plan import PAUSED, PendingPlan
from agent_runtime.domain.turn.prior_run import PriorRun
from tests.agent_runtime.domain.builders import REPORT

ECHOED = Action("echo", "", True, "ok")


def test_a_proposed_plan_is_shown_as_it_was_written() -> None:
    proposed = PendingPlan(REPORT)

    assert not proposed.is_paused
    assert proposed.render() == REPORT.render()


def test_a_plan_with_a_prior_run_is_paused() -> None:
    assert PendingPlan(REPORT, PriorRun(1, (ECHOED,))).is_paused


def test_a_paused_plan_is_shown_with_its_progress_and_expected_result() -> None:
    shown = PendingPlan(REPORT, PriorRun(1)).render()

    assert shown.splitlines()[:3] == [
        PAUSED,
        "✓ 1. count (tool: echo)",
        "→ 2. write (tool: file_writer)",
    ]
    assert shown.endswith("### Expected result\nA report.")
