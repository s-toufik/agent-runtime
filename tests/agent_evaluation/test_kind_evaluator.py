from agent_evaluation.application.kind_suite import KindSuite
from agent_evaluation.domain.case import Case, Say
from agent_evaluation.domain.check.text_checks import Contains
from agent_evaluation.domain.exception import AgentUnavailable
from agent_evaluation.domain.kind import Kind
from agent_evaluation.domain.result import Status
from tests.agent_evaluation.fakes import RecordingClock, ScriptedAgent, evaluator, policy, reply

ASK_PARIS = Case("capital", "Capital of France", (Say("Capital of France?", (Contains("Paris"),)),))


def _suite(*cases: Case, **changes) -> KindSuite:
    skipped = changes.pop("skipped", frozenset())
    return KindSuite(Kind.RELEVANCE, cases, policy(**changes), skipped)


async def test_each_case_runs_the_configured_number_of_times_with_pauses() -> None:
    agent, clock = ScriptedAgent(reply()), RecordingClock()
    other = Case("other", "Other", (Say("again?"),))

    result = await evaluator(agent, clock).evaluate(_suite(ASK_PARIS, other, runs=3))

    assert [case.status for case in result.cases] == [Status.PASSED, Status.PASSED]
    assert len(agent.sent) == 6
    assert clock.sleeps == [5.0, 5.0, 10.0, 5.0, 5.0]


async def test_messages_of_a_case_share_one_conversation_and_pause_between_them() -> None:
    agent, clock = ScriptedAgent(reply()), RecordingClock()
    case = Case(
        "chat",
        "Two messages, two conversations",
        (Say("one {run_id}"), Say("two"), Say("elsewhere", conversation="other")),
    )

    await evaluator(agent, clock).evaluate(_suite(case, runs=1))

    (first, one), (_, two), (_, elsewhere) = [(m, c) for m, c, _ in agent.sent]
    assert one == two != elsewhere
    assert "{run_id}" not in first and one.endswith("-main")
    assert clock.sleeps == [1.0, 1.0]


async def test_a_case_passes_when_enough_of_its_runs_pass_and_is_flagged_flaky() -> None:
    agent = ScriptedAgent(reply("Paris"), reply("Lyon"), reply("Lyon"))
    suite = _suite(ASK_PARIS, runs=3, case_pass_rate=0.6)

    case = (await evaluator(agent, RecordingClock()).evaluate(suite)).cases[0]

    assert case.status is Status.FAILED and case.is_flaky and case.passed_runs == 1


async def test_a_case_override_sets_its_own_runs_and_pause() -> None:
    agent, clock = ScriptedAgent(reply()), RecordingClock()
    case = Case("own", "Own policy", (Say("?"),), runs=2, pause_between_runs_seconds=60)

    await evaluator(agent, clock).evaluate(_suite(case, runs=5))

    assert len(agent.sent) == 2 and clock.sleeps == [60]


async def test_forced_runs_win_over_the_case() -> None:
    agent = ScriptedAgent(reply())
    case = Case("own", "Own policy", (Say("?"),), runs=4)

    await evaluator(agent, RecordingClock()).evaluate(_suite(case, forced_runs=1))

    assert len(agent.sent) == 1


async def test_an_unavailable_agent_is_retried_then_reported_as_an_error() -> None:
    agent, clock = ScriptedAgent(AgentUnavailable("HTTP 503")), RecordingClock()

    case = (await evaluator(agent, clock).evaluate(_suite(ASK_PARIS, runs=1))).cases[0]

    assert case.status is Status.ERROR and "HTTP 503" in case.reason
    assert case.runs[0].attempts == 2 and clock.sleeps == [30.0]


async def test_a_retry_that_succeeds_counts_as_a_normal_run() -> None:
    agent = ScriptedAgent(AgentUnavailable("overloaded"), reply())

    case = (await evaluator(agent, RecordingClock()).evaluate(_suite(ASK_PARIS, runs=1))).cases[0]

    assert case.status is Status.PASSED and case.runs[0].attempts == 2


async def test_cases_needing_a_missing_capability_or_skipped_in_the_panel_are_not_run() -> None:
    agent = ScriptedAgent(reply())
    jira = Case("jira", "Needs Jira", (Say("tickets?"),), requires=("jira",))
    no_jira = Case("no-jira", "Only without Jira", (Say("ticket?"),), unless=("jira",))
    muted = Case("muted", "Muted", (Say("?"),))

    result = await evaluator(agent, RecordingClock()).evaluate(
        _suite(jira, no_jira, muted, runs=1, skipped=frozenset({"muted"}))
    )

    assert [case.status for case in result.cases] == [Status.SKIPPED, Status.PASSED, Status.SKIPPED]
    assert result.cases[0].reason == "needs jira (not available)"
    assert result.cases[2].reason == "skipped in the control panel"
    assert len(agent.sent) == 1 and result.status is Status.PASSED
