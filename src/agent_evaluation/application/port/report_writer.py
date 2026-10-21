from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol

from agent_evaluation.domain.kind import Kind
from agent_evaluation.domain.result import KindResult


class ReportWriter(Protocol):
    def write_kind(self, result: KindResult) -> tuple[Path, ...]: ...

    def write_overall(self, results: tuple[KindResult, ...]) -> Path: ...


class KindJournal(Protocol):
    def recording(self, kind: Kind) -> AbstractContextManager[Path]: ...
