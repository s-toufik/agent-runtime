import json
from pathlib import Path

from agent_evaluation.adapter.report.json_report import kind_document
from agent_evaluation.adapter.report.markdown_report import kind_markdown
from agent_evaluation.adapter.report.overall_report import overall_markdown
from agent_evaluation.adapter.report.report_header import ReportHeader
from agent_evaluation.adapter.report.report_paths import ReportPaths
from agent_evaluation.domain.result import KindResult


class FileReportWriter:
    def __init__(self, paths: ReportPaths, header: ReportHeader) -> None:
        self._paths = paths
        self._header = header
        self._markdown: dict[str, Path] = {}

    def write_kind(self, result: KindResult) -> tuple[Path, ...]:
        self._paths.directory.mkdir(parents=True, exist_ok=True)
        raw = self._paths.kind(result.kind, "json")
        raw.write_text(
            json.dumps(kind_document(self._header, result), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        report = self._paths.kind(result.kind, "md")
        report.write_text(kind_markdown(self._header, result), encoding="utf-8")
        self._markdown[str(result.kind)] = report
        return raw, report

    def write_overall(self, results: tuple[KindResult, ...]) -> Path:
        self._paths.directory.mkdir(parents=True, exist_ok=True)
        path = self._paths.overall()
        path.write_text(overall_markdown(self._header, results, self._markdown), encoding="utf-8")
        return path
