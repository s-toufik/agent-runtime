from dataclasses import asdict
from typing import Any

from agent_evaluation.adapter.report.report_header import ReportHeader
from agent_evaluation.domain.case import Case
from agent_evaluation.domain.result import CaseResult, ExchangeResult, KindResult, RunResult, Status


def kind_document(header: ReportHeader, result: KindResult) -> dict[str, Any]:
    return {
        "kind": str(result.kind),
        "status": str(result.status),
        "started_at": result.started_at.isoformat(),
        "finished_at": result.finished_at.isoformat(),
        "agent": {"url": header.agent_url, "model": header.model_name},
        "judge": {"model": header.judge_model, "pass_score": header.pass_score},
        "panel": header.panel,
        "policy": asdict(result.policy),
        "summary": summary(result),
        "cases": [_case(case) for case in result.cases],
    }


def summary(result: KindResult) -> dict[str, Any]:
    return {
        "cases": len(result.cases),
        "executed": result.executed,
        "passed": result.count(Status.PASSED),
        "failed": result.count(Status.FAILED),
        "errors": result.count(Status.ERROR),
        "skipped": result.count(Status.SKIPPED),
        "flaky": [case.case.id for case in result.flaky],
        "runs": len(result.runs),
        "run_pass_rate": result.run_pass_rate,
        "mean_seconds": result.mean_seconds,
        "p95_seconds": result.p95_seconds,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "mean_judge_score": result.mean_judge_score,
        "failing_checks": dict(result.failing_checks),
    }


def _case(result: CaseResult) -> dict[str, Any]:
    return {
        **_definition(result.case),
        "status": str(result.status),
        "reason": result.reason,
        "passed_runs": result.passed_runs,
        "pass_rate": result.pass_rate,
        "flaky": result.is_flaky,
        "runs": [_run(run) for run in result.runs],
    }


def _definition(case: Case) -> dict[str, Any]:
    return {
        "id": case.id,
        "title": case.title,
        "requires": list(case.requires),
        "unless": list(case.unless),
        "messages": [say.message for say in case.says],
    }


def _run(run: RunResult) -> dict[str, Any]:
    return {
        "number": run.number,
        "status": str(run.status),
        "run_id": run.run_id,
        "attempts": run.attempts,
        "started_at": run.started_at.isoformat(),
        "seconds": round(run.seconds, 3),
        "error": run.error,
        "exchanges": [_exchange(exchange) for exchange in run.exchanges],
    }


def _exchange(result: ExchangeResult) -> dict[str, Any]:
    exchange = result.exchange
    return {
        "conversation": exchange.conversation,
        "message": exchange.message,
        "auto_approve": exchange.auto_approve,
        "reply": asdict(exchange.reply),
        "checks": [asdict(check) for check in result.checks],
    }
