import json
from pathlib import Path

import pytest

from agent_evaluation.adapter.journal.file_journal import FileJournal
from agent_evaluation.adapter.report.file_report_writer import FileReportWriter
from agent_evaluation.adapter.report.report_header import ReportHeader
from agent_evaluation.adapter.report.report_paths import ReportPaths
from agent_evaluation.application.evaluation import Evaluation
from agent_evaluation.application.kind_suite import KindSuite
from agent_evaluation.domain.case import Case, Say
from agent_evaluation.domain.check.judged import Judged
from agent_evaluation.domain.check.text_checks import Contains
from agent_evaluation.domain.exception import AgentUnavailable
from agent_evaluation.domain.kind import Kind
from tests.agent_evaluation.fakes import (
    STARTED,
    FixedJudge,
    RecordingClock,
    ScriptedAgent,
    evaluator,
    policy,
    reply,
)

PASSING = Case("capital", "Capital of France", (Say("Capital?", (Contains("Paris"),)),))
FAILING = Case(
    "judged",
    "Judged | answer",
    (Say("Explain", (Judged("Explains well."), Contains("Lyon"))),),
)
NEEDS_JIRA = Case("jira", "Needs Jira", (Say("?"),), requires=("jira",))


def _evaluation(tmp_path: Path, agent: ScriptedAgent) -> Evaluation:
    clock = RecordingClock()
    paths = ReportPaths(tmp_path, STARTED)
    header = ReportHeader(STARTED, "http://agent/v1/stream", "m", "judge", 0.7, "panel.json")
    return Evaluation(
        agent,
        evaluator(agent, clock, FixedJudge(0.4, "too vague")),
        FileReportWriter(paths, header),
        FileJournal(paths),
        clock,
    )


async def test_every_kind_writes_json_markdown_and_log_plus_an_overall_report(tmp_path) -> None:
    suites = (
        KindSuite(Kind.ROUTING, (PASSING, NEEDS_JIRA), policy(runs=2)),
        KindSuite(Kind.QUALITY, (FAILING,), policy(runs=1)),
    )

    outcome = await _evaluation(tmp_path, ScriptedAgent(reply("Paris"))).run(suites)

    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "20261020_153012_OVERALL.md",
        "20261020_153012_QUALITY.json",
        "20261020_153012_QUALITY.log",
        "20261020_153012_QUALITY.md",
        "20261020_153012_ROUTING.json",
        "20261020_153012_ROUTING.log",
        "20261020_153012_ROUTING.md",
    ]
    assert outcome.overall.name == "20261020_153012_OVERALL.md"

    raw = json.loads((tmp_path / "20261020_153012_ROUTING.json").read_text())
    assert raw["summary"]["passed"] == 1 and raw["summary"]["skipped"] == 1
    assert raw["cases"][0]["runs"][0]["exchanges"][0]["reply"]["content"] == "Paris"

    report = (tmp_path / "20261020_153012_QUALITY.md").read_text()
    assert "# QUALITY: ❌ FAILED" in report and "too vague" in report
    assert 'missing "Lyon"' in report and "Judged \\| answer" in report

    log = (tmp_path / "20261020_153012_QUALITY.log").read_text()
    assert "judged run 1" in log and "FAIL [0.40] judge: Explains well." in log
    assert "ROUTING" not in log

    overall = (tmp_path / "20261020_153012_OVERALL.md").read_text()
    assert "1 / 2 kinds passed" in overall
    assert "[20261020_153012_QUALITY.md](20261020_153012_QUALITY.md)" in overall
    assert "**QUALITY** `judged`: FAILED" in overall


async def test_an_agent_that_fails_preflight_stops_before_any_case(tmp_path) -> None:
    class Down(ScriptedAgent):
        async def preflight(self) -> None:
            raise AgentUnavailable("not reachable")

    agent = Down(reply())

    with pytest.raises(AgentUnavailable):
        await _evaluation(tmp_path, agent).run((KindSuite(Kind.ROUTING, (PASSING,), policy()),))
    assert agent.sent == [] and list(tmp_path.iterdir()) == []
