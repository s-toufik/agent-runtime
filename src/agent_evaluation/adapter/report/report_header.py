from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ReportHeader:
    started_at: datetime
    agent_url: str
    model_name: str
    judge_model: str
    pass_score: float
    panel: str
