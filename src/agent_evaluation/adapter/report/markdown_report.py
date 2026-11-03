from agent_evaluation.adapter.report.formatting import (
    cell,
    excerpt,
    percent,
    score,
    seconds,
    tokens,
)
from agent_evaluation.adapter.report.report_header import ReportHeader
from agent_evaluation.domain.result import CaseResult, KindResult, RunResult, Status

ICONS: dict[Status, str] = {
    Status.PASSED: "✅",
    Status.FAILED: "❌",
    Status.ERROR: "⚠️",
    Status.SKIPPED: "⏭️",
}


def kind_markdown(header: ReportHeader, result: KindResult) -> str:
    sections = [
        _title(header, result),
        _result(result),
        _cases(result),
        _failures(result),
        _failing_checks(result),
        _skipped(result),
    ]
    return "\n\n".join(section for section in sections if section) + "\n"


def _title(header: ReportHeader, result: KindResult) -> str:
    policy = result.policy
    return "\n".join(
        [
            f"# {result.kind}: {ICONS[result.status]} {result.status}",
            "",
            "| | |",
            "|---|---|",
            f"| Date | {result.started_at:%Y-%m-%d %H:%M:%S} → {result.finished_at:%H:%M:%S} |",
            f"| Agent | {header.agent_url} |",
            f"| Model | {header.model_name} |",
            f"| Judge | {header.judge_model} (pass score {header.pass_score:.2f}) |",
            f"| Runs per case | {policy.runs} by default, "
            f"{policy.pause_between_runs_seconds:g} s between runs |",
            f"| Pauses | {policy.pause_between_messages_seconds:g} s between messages, "
            f"{policy.pause_between_cases_seconds:g} s between cases |",
            f"| A case passes when | at least {percent(policy.case_pass_rate)} of its runs pass |",
            f"| Control panel | {header.panel} |",
        ]
    )


def _result(result: KindResult) -> str:
    flaky = len(result.flaky)
    return "\n".join(
        [
            "## Result",
            "",
            f"**{result.count(Status.PASSED)} / {result.executed} cases passed** · "
            f"{result.count(Status.FAILED)} failed · {result.count(Status.ERROR)} errors · "
            f"{result.count(Status.SKIPPED)} skipped · {flaky} flaky",
            "",
            f"- Runs: {sum(run.status is Status.PASSED for run in result.runs)}"
            f" / {len(result.runs)} passed ({percent(result.run_pass_rate)})",
            f"- Agent latency per message: mean {seconds(result.mean_seconds)}, "
            f"p95 {seconds(result.p95_seconds)}",
            f"- Tokens: {tokens(result.input_tokens)} in / {tokens(result.output_tokens)} out",
            f"- Mean judge score: {score(result.mean_judge_score)}",
        ]
    )


def _cases(result: KindResult) -> str:
    rows = [
        "## Cases",
        "",
        "| Case | Status | Runs passed | Mean latency | Title |",
        "|---|---|---|---|---|",
    ]
    for case in result.cases:
        runs = "-" if case.status is Status.SKIPPED else f"{case.passed_runs}/{len(case.runs)}"
        flaky = " (flaky)" if case.is_flaky else ""
        mean = (
            sum(reply.seconds for reply in case.replies) / len(case.replies)
            if case.replies
            else None
        )
        rows.append(
            f"| `{case.case.id}` | {ICONS[case.status]} {case.status}{flaky} | {runs} "
            f"| {seconds(mean)} | {cell(case.case.title)} |"
        )
    return "\n".join(rows)


def _failures(result: KindResult) -> str:
    failing = [
        case
        for case in result.cases
        if case.status in (Status.FAILED, Status.ERROR) or case.is_flaky
    ]
    if not failing:
        return ""
    return "\n\n".join(["## Failures and flaky cases", *(_failure(case) for case in failing)])


def _failure(case: CaseResult) -> str:
    lines = [f"### `{case.case.id}`: {case.case.title}"]
    for run in case.runs:
        if run.status is Status.PASSED:
            continue
        lines.append("")
        lines.append(f"**Run {run.number}: {run.status}** ({seconds(run.seconds)})")
        lines.extend(_run_details(run))
    return "\n".join(lines)


def _run_details(run: RunResult) -> list[str]:
    if run.status is Status.ERROR:
        return [f"- ⚠️ {run.error}"]
    lines: list[str] = []
    for index, result in enumerate(run.exchanges, 1):
        failed = [check for check in result.checks if not check.passed]
        if not failed:
            continue
        reply = result.exchange.reply
        lines.append(f"- Message {index}: _{cell(excerpt(result.exchange.message, 160))}_")
        for check in failed:
            graded = f" (score {check.score:.2f})" if check.score is not None else ""
            lines.append(f"  - ✗ {check.label}{graded}: {check.detail}")
        lines.append(
            f"  - Answer ({reply.outcome or 'no outcome'}, tools: "
            f"{', '.join(reply.tools) or 'none'}): {excerpt(reply.content)}"
        )
    return lines


def _failing_checks(result: KindResult) -> str:
    failing = result.failing_checks
    if not failing:
        return ""
    rows = ["## Checks that failed most", "", "| Check | Failed runs |", "|---|---|"]
    rows.extend(f"| {cell(label)} | {count} |" for label, count in failing[:15])
    return "\n".join(rows)


def _skipped(result: KindResult) -> str:
    skipped = [case for case in result.cases if case.status is Status.SKIPPED]
    if not skipped:
        return ""
    return "\n".join(
        ["## Skipped", "", *(f"- `{case.case.id}`: {case.reason}" for case in skipped)]
    )
