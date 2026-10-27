from agent_runtime.adapter.outbound.llm.langchain.prompts import act, clock, plan
from agent_runtime.adapter.outbound.llm.langchain.prompts.act import (
    act_feedback,
    act_system_prompt,
    next_step_request,
)
from agent_runtime.adapter.outbound.llm.langchain.prompts.context import (
    context_request,
    context_system_prompt,
)
from agent_runtime.adapter.outbound.llm.langchain.prompts.plan import plan_system_prompt
from agent_runtime.adapter.outbound.llm.langchain.prompts.review import (
    reflection_request,
    reflection_system_prompt,
)
from agent_runtime.adapter.outbound.llm.langchain.prompts.summary import summary_request
from agent_runtime.adapter.outbound.llm.langchain.prompts.tool_catalog import NO_TOOLS
from agent_runtime.domain.tool.tool_result import ToolResult
from agent_runtime.domain.tool.tool_specification import ToolSpecification
from agent_runtime.domain.turn.action import Action
from agent_runtime.domain.turn.pending_plan import PendingPlan
from agent_runtime.domain.turn.plan import Plan, PlannedStep
from agent_runtime.domain.turn.plan_progress import PlanProgress
from agent_runtime.domain.turn.prior_run import PriorRun

TOOLS = [ToolSpecification("run_sql", "SQL.")]
PLAN = Plan("q", (PlannedStep("count rows", "run_sql"), PlannedStep("write report", "file_writer")))
STARTED = PlanProgress.of(PLAN, [])
FINISHED = PlanProgress.of(
    PLAN, [ToolResult("1", "run_sql", "3"), ToolResult("2", "file_writer", "ok")]
)


def test_the_act_prompt_describes_tool_work_only_under_a_plan() -> None:
    assert "approved this plan" in act_system_prompt("q", STARTED, TOOLS)
    assert "cannot run tools" in act_system_prompt("q", None, TOOLS)
    assert "- run_sql: SQL." in act_system_prompt("q", None, TOOLS)
    assert NO_TOOLS in act_system_prompt("q", None, [])


def test_under_a_plan_the_act_prompt_shows_the_progress_and_names_the_next_step() -> None:
    prompt = act_system_prompt("q", STARTED, TOOLS)

    assert "→ 1. count rows (tool: run_sql)\n· 2. write report (tool: file_writer)" in prompt
    assert next_step_request(STARTED) == (
        "Now do step 1: count rows\n"
        "Call run_sql to do it. Do not describe the step instead of running it."
    )


def test_once_every_step_is_done_the_act_prompt_asks_for_the_answer() -> None:
    prompt = act_system_prompt("q", FINISHED, TOOLS)

    assert "All steps of the approved plan are done" in prompt
    assert "✓ 2. write report" in prompt
    assert next_step_request(FINISHED) is None


def test_the_act_prompt_links_plots_from_reports() -> None:
    assert "![Title](plot.svg)" in act_system_prompt("q", STARTED, TOOLS)


def test_the_plan_prompt_lists_the_tools_the_schema_and_the_plan_to_revise() -> None:
    prompt = plan_system_prompt("count users", TOOLS, "SCHEMA", PendingPlan(PLAN))

    assert "count users" in prompt and "- run_sql: SQL." in prompt and PLAN.render() in prompt
    assert "SCHEMA" in prompt and "exactly one tool call" in prompt
    assert "Reuse the work done earlier" in prompt
    assert NO_TOOLS in plan_system_prompt("q", [], "SCHEMA")


def test_prompts_carry_the_current_time(monkeypatch) -> None:
    monkeypatch.setattr(clock, "utc_now", lambda: "2026-01-01 00:00 UTC")
    monkeypatch.setattr(act, "utc_now", lambda: "2026-01-01 00:00 UTC")
    monkeypatch.setattr(plan, "utc_now", lambda: "2026-01-01 00:00 UTC")

    assert "2026-01-01 00:00 UTC" in act_system_prompt("q", None, [])
    assert "2026-01-01 00:00 UTC" in plan_system_prompt("q", [], "SCHEMA")


def test_structured_prompts_embed_their_output_schema() -> None:
    assert "SCHEMA" in context_system_prompt("SCHEMA")
    assert "SCHEMA" in reflection_system_prompt("SCHEMA", has_evidence=True)


def test_requests_fall_back_to_none_when_a_part_is_missing() -> None:
    assert "(none)" in context_request("(none)", None, "hi")
    review = reflection_request("c", "q", [], None, [], [], "")
    assert review.count("(none)") == 4 and "(empty answer)" in review
    assert "(none)" in summary_request("", "User: hi")


def test_feedback_quotes_the_critique() -> None:
    assert "too short" in act_feedback("too short")


def test_the_context_prompt_checks_for_a_task_before_a_rework_or_a_direct_answer() -> None:
    prompt = context_system_prompt("SCHEMA")

    assert "Pick the FIRST intent" in prompt
    assert prompt.index("task:") < prompt.index("rework:") < prompt.index("direct:")
    assert "questions about the assistant itself" in prompt


def test_the_context_prompt_keeps_general_knowledge_questions_direct() -> None:
    prompt = context_system_prompt("SCHEMA")

    assert "the user's own data, files, records or systems" in prompt
    assert "alternatives or good practices, even when\n   technical" in prompt
    assert '"are there alternatives to Kafka?" -> direct' in prompt


def test_the_review_holds_an_answer_to_the_tool_evidence_only_when_a_tool_ran() -> None:
    grounded = reflection_system_prompt("SCHEMA", has_evidence=True)
    ungrounded = reflection_system_prompt("SCHEMA", has_evidence=False)

    assert "not in the tool evidence" in grounded and "general knowledge" not in grounded
    assert "may use general knowledge" in ungrounded and "tool evidence" not in ungrounded


def test_without_a_plan_the_act_prompt_asks_for_a_plan_through_its_tool() -> None:
    assert "call request_plan instead of answering" in act_system_prompt("q", None, [])
    assert "request_plan" not in act_system_prompt("q", STARTED, [])


def test_the_review_rejects_claims_of_work_the_tool_calls_do_not_show() -> None:
    assert "the tool\n  calls do not show" in reflection_system_prompt("SCHEMA", has_evidence=True)
    review = reflection_request("c", "q", [], "✓ 1. x", ["echo(): ok -> hi"], [], "a")
    assert "- echo(): ok -> hi" in review and "✓ 1. x" in review


def test_the_act_prompt_asks_for_aligned_text_diagrams_not_mermaid() -> None:
    prompt = act_system_prompt("explain the stack", None, [])

    assert "```text" in prompt
    assert "never Mermaid" in prompt
    assert "►" in prompt and "Never use ▶ or ◀" in prompt


ECHOED = Action("echo", "text='hi'", True, "hi")
PAUSED_AFTER_ONE = PendingPlan(PLAN, PriorRun(1, (ECHOED,)))


def test_the_context_prompt_reads_continue_as_approving_a_paused_plan() -> None:
    prompt = context_system_prompt("SCHEMA")

    assert '"continue" (with a paused plan pending) -> plan_approval' in prompt
    assert '"make it shorter" -> rework' in prompt


def test_a_paused_plan_is_revised_into_only_what_is_left() -> None:
    paused = plan_system_prompt("q", TOOLS, "SCHEMA", PAUSED_AFTER_ONE)
    proposed = plan_system_prompt("q", TOOLS, "SCHEMA", PendingPlan(PLAN))

    assert "✓ 1. count rows" in paused and "plan only what is left" in paused
    assert "plan only what is left" not in proposed


def test_the_act_prompt_tells_a_resumed_plan_what_already_ran() -> None:
    resumed = act_system_prompt("q", PlanProgress(PLAN, 1), TOOLS, PAUSED_AFTER_ONE.prior)
    fresh = act_system_prompt("q", STARTED, TOOLS)

    assert "do not run them again" in resumed and "- echo(text='hi'): ok -> hi" in resumed
    assert "paused at the step limit" not in fresh
    assert "paused at the step limit" in act_system_prompt("q", FINISHED, TOOLS, PriorRun(1))


def test_the_review_lists_the_plan_s_earlier_tool_calls_only_when_it_was_resumed() -> None:
    resumed = reflection_request("c", "q", [], None, [], [], "a", prior_actions=["echo(): ok"])

    assert "in earlier turns" in resumed and "- echo(): ok" in resumed
    assert "in earlier turns" not in reflection_request("c", "q", [], None, [], [], "a")
