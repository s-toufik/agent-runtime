from agent_runtime.domain.agent.peer_reply import PeerOutcome, PeerReply
from agent_runtime.domain.event.progress import Progress, ProgressKind, StepState
from agent_runtime.domain.tool.tool_call import ToolCall
from agent_runtime.domain.tool.tool_result import ToolResult
from agent_runtime.domain.turn.plan import Plan, PlannedStep
from agent_runtime.domain.turn.plan_progress import PlanProgress

PLAN = Plan(
    "read caddy's logs",
    (
        PlannedStep("Find caddy's pod", "kubectl_get"),
        PlannedStep("Read its last logs", "loki_query"),
        PlannedStep("Sum up what they say"),
    ),
)


def test_a_plan_shows_which_steps_are_done_current_and_still_to_do() -> None:
    progress = Progress.plan(PlanProgress(PLAN, done=1))

    assert progress.kind is ProgressKind.PLAN
    assert [(s.number, s.tool, s.state) for s in progress.steps] == [
        (1, "kubectl_get", StepState.DONE),
        (2, "loki_query", StepState.CURRENT),
        (3, None, StepState.TO_DO),
    ]
    assert [s.state for s in Progress.plan(PlanProgress(PLAN, done=3)).steps] == [
        StepState.DONE
    ] * 3


def test_a_tool_call_says_what_it_runs_and_how_it_ended() -> None:
    started = Progress.tool_started(ToolCall("c1", "loki_query", {"query": '{app="caddy"}'}))
    failed = Progress.tool_finished(ToolResult.failure("c1", "loki_query", "Loki timed out"))

    assert (started.name, started.state, started.detail) == (
        "loki_query",
        "running",
        '{"query": "{app=\\"caddy\\"}"}',
    )
    assert (failed.state, failed.detail) == ("failed", "Loki timed out")
    assert Progress.tool_finished(ToolResult("c1", "loki_query", "ok")).state == "done"


def test_long_details_are_cut_to_one_line() -> None:
    progress = Progress.tool_started(ToolCall("c1", "echo", {"text": "word\n" * 100}))

    assert "\n" not in progress.detail
    assert len(progress.detail) == 160
    assert progress.detail.endswith("…")


def test_what_another_agent_does_is_placed_under_its_name() -> None:
    inner = Progress.agent_started("analysis", "count rows").under("observation")

    assert inner.path == ("observation",)
    assert inner.under("supervisor").path == ("supervisor", "observation")
    finished = Progress.agent_finished(PeerReply("analysis", PeerOutcome.NEEDS_INPUT, "?"))
    assert (finished.name, finished.state) == ("analysis", "needs_input")


def test_progress_travels_as_json_and_comes_back_the_same() -> None:
    for progress in (
        Progress.plan(PlanProgress(PLAN, done=1)).under("observation"),
        Progress.tool_started(ToolCall("c1", "loki_query", {"query": "x"})),
        Progress.agent_started("kitchen", "dinner"),
    ):
        assert Progress.from_json(progress.to_json()) == progress


def test_unreadable_progress_is_ignored() -> None:
    assert Progress.from_json("not json") is None
    assert Progress.from_dict({"kind": "weather"}) is None
    assert Progress.from_dict(["plan"]) is None
