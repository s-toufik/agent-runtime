import logging
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from agent_evaluation.adapter.report.report_paths import ReportPaths
from agent_evaluation.domain.kind import Kind

ROOT_LOGGER: str = "agent_evaluation"
FORMAT: str = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"


class FileJournal:
    def __init__(self, paths: ReportPaths) -> None:
        self._paths = paths

    @contextmanager
    def recording(self, kind: Kind) -> Generator[Path]:
        path = self._paths.kind(kind, "log")
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter(FORMAT))
        root = logging.getLogger(ROOT_LOGGER)
        level = root.level
        root.setLevel(logging.DEBUG)
        root.addHandler(handler)
        try:
            yield path
        finally:
            root.removeHandler(handler)
            root.setLevel(level)
            handler.close()
