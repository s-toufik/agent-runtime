from pathlib import Path

from agent_evaluation.adapter.report.formatting import percent, score, seconds, tokens
from agent_evaluation.adapter.report.markdown_report import ICONS
from agent_evaluation.adapter.report.report_header import ReportHeader
from agent_evaluation.domain.result import KindResult, Status


def overall_markdown(
    header: ReportHeader, results: tuple[KindResult, ...], reports: dict[str, Path]
) -> str:
    executed = [result for result in results if result.status is not Status.SKIPPED]
    passed_kinds = sum(result.status is Status.PASSED for result in executed)
    cases = sum(result.executed for result in results)
    passed_cases = sum(result.count(Status.PASSED) for result in results)
    runs = [run for result in results for run in result.runs]
    passed_runs = sum(run.status is Status.PASSED for run in runs)
    lines = [
        f"# Agent evaluation: {passed_kinds} / {len(executed)} kinds passed",
        "",
        "| | |",
        "|---|---|",
        f"| Date | {header.started_at:%Y-%m-%d %H:%M:%S} |",
        f"| Agent | {header.agent_url} |",
        f"| Model | {header.model_name} |",
        f"| Judge | {header.judge_model} (pass score {header.pass_score:.2f}) |",
        f"| Control panel | {header.panel} |",
        "",
        f"**{passed_cases} / {cases} cases passed** · "
        f"{passed_runs} / {len(runs)} runs passed "
        f"({percent(passed_runs / len(runs) if runs else None)})",
        "",
        "## By kind",
        "",
        "| Kind | Status | Cases passed | Failed | Errors | Skipped | Flaky | Run pass rate "
        "| Mean latency | Tokens in/out | Judge score | Report |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        report = reports.get(str(result.kind))
        link = f"[{report.name}]({report.name})" if report else "-"
        lines.append(
            f"| {result.kind} | {ICONS[result.status]} {result.status} "
            f"| {result.count(Status.PASSED)}/{result.executed} | {result.count(Status.FAILED)} "
            f"| {result.count(Status.ERROR)} | {result.count(Status.SKIPPED)} "
            f"| {len(result.flaky)} | {percent(result.run_pass_rate)} "
            f"| {seconds(result.mean_seconds)} "
            f"| {tokens(result.input_tokens)}/{tokens(result.output_tokens)} "
            f"| {score(result.mean_judge_score)} | {link} |"
        )
    attention = [
        f"- **{result.kind}** `{case.case.id}`: {case.status}"
        + (" (flaky)" if case.is_flaky else "")
        + f", {case.passed_runs}/{len(case.runs)} runs passed: {case.case.title}"
        for result in results
        for case in result.cases
        if case.status in (Status.FAILED, Status.ERROR) or case.is_flaky
    ]
    if attention:
        lines.extend(["", "## Needs attention", "", *attention])
    return "\n".join(lines) + "\n"
