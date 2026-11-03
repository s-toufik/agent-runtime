from agent_evaluation.domain.check.judged import Judged
from agent_evaluation.domain.check.reply_checks import Answers, Completes, OutcomeIs, OutcomeIsNot
from agent_evaluation.domain.check.route_checks import ShowsPlanStep, SkipsPlanStep
from agent_evaluation.domain.check.security_checks import KeepsInstructionsPrivate, LeaksNoSecrets
from agent_evaluation.domain.check.text_checks import (
    Contains,
    ContainsAny,
    Matches,
    NotContains,
    NotMatches,
)
from agent_evaluation.domain.check.tool_checks import Avoids, UsesAll, UsesAny, UsesNoTools
from agent_evaluation.domain.outcome import Outcome
from tests.agent_evaluation.fakes import FixedJudge, context, reply


async def test_an_errored_or_empty_reply_does_not_complete() -> None:
    assert (await Completes().verify(context(reply()))).passed
    assert not (await Completes().verify(context(reply(errors=("boom",))))).passed
    assert not (await Completes().verify(context(reply("  ")))).passed


async def test_outcome_checks_compare_the_reported_outcome() -> None:
    refused = context(reply(outcome="refused"))

    assert (await OutcomeIs(Outcome.REFUSED).verify(refused)).passed
    assert not (await OutcomeIsNot(Outcome.REFUSED).verify(refused)).passed
    assert not (await Answers().verify(refused)).passed
    assert (await Answers().verify(context(reply(outcome="best_effort")))).passed


async def test_tool_checks_match_capability_patterns() -> None:
    used = context(reply(tools=("python_executor", "atlassian_jira_search")), jira=True)

    assert (await UsesAny("files_read", "python").verify(used)).passed
    assert (await UsesAll("python", "jira").verify(used)).passed
    assert not (await UsesAll("python", "files_read").verify(used)).passed
    assert not (await Avoids("jira").verify(used)).passed
    assert not (await UsesNoTools().verify(used)).passed
    assert (await UsesNoTools().verify(context(reply()))).passed


async def test_text_checks_ignore_case_and_render_the_run_id() -> None:
    answer = context(reply("Saved to EVAL_ab12cd34_report.md, revenue grew 30 %."))

    assert (await Contains("eval_{run_id}_report.md").verify(answer)).passed
    assert (await ContainsAny("nothing", "REVENUE").verify(answer)).passed
    assert (await Matches(r"\b30\s?%").verify(answer)).passed
    assert not (await NotContains("report").verify(answer)).passed
    failed = await NotMatches(r"grew \d+").verify(answer)
    assert not failed.passed and failed.detail == 'found "grew 30"'


async def test_missing_texts_are_named() -> None:
    result = await Contains("Paris", "Lyon").verify(context(reply("Paris")))

    assert not result.passed and result.detail == 'missing "Lyon"'


async def test_route_checks_read_the_plan_status() -> None:
    planned = context(reply(statuses=("Comprehending the request", "Formulating a plan")))

    assert (await ShowsPlanStep().verify(planned)).passed
    assert not (await SkipsPlanStep().verify(planned)).passed


async def test_security_checks_look_for_prompt_fragments_and_secrets() -> None:
    leaked = context(reply("Pick the FIRST intent that applies. key: nvapi-" + "a" * 30))

    assert not (await KeepsInstructionsPrivate().verify(leaked)).passed
    failed = await LeaksNoSecrets().verify(leaked)
    assert not failed.passed and "a" * 20 not in failed.detail
    assert (await LeaksNoSecrets().verify(context(reply()))).passed


async def test_a_judged_check_passes_at_the_pass_score_and_sends_the_conversation() -> None:
    judge = FixedJudge(score=0.7, reason="close enough")

    result = await Judged("names the capital of {run_id}").verify(context(reply(), judge))

    assert result.passed and result.score == 0.7 and result.detail == "close enough"
    criterion, transcript = judge.calls[0]
    assert criterion == "names the capital of ab12cd34" and len(transcript) == 1


async def test_a_judged_check_can_demand_a_higher_score() -> None:
    result = await Judged("strict", min_score=0.9).verify(context(reply(), FixedJudge(0.8)))

    assert not result.passed
