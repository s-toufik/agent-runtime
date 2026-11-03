from datetime import datetime
from pathlib import Path

from agent_evaluation.domain.kind import Kind

OVERALL: str = "OVERALL"


class ReportPaths:
    def __init__(self, directory: Path, started_at: datetime) -> None:
        self.directory = directory
        self.stamp: str = started_at.strftime("%Y%m%d_%H%M%S")

    def kind(self, kind: Kind, suffix: str) -> Path:
        return self.directory / f"{self.stamp}_{kind}.{suffix}"

    def overall(self) -> Path:
        return self.directory / f"{self.stamp}_{OVERALL}.md"
