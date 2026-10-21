import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agent_evaluation.domain.kind import Kind


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentSection(_Section):
    base_url: str
    endpoint: str = "/v1/stream"
    models_endpoint: str | None = "/v1/models"
    model_name: str
    timeout_seconds: float = Field(default=900.0, gt=0)
    headers: dict[str, str] = Field(default_factory=dict)


class JudgeSection(_Section):
    base_url: str
    model_name: str
    api_key_env: str | None = None
    env_file: str | None = ".env"
    temperature: float = 0.0
    max_output_tokens: int = Field(default=2048, gt=0)
    max_context_tokens: int = Field(default=32768, gt=0)
    reasoning_effort: Literal["low", "medium", "high"] | None = None
    pass_score: float = Field(default=0.7, ge=0.0, le=1.0)
    pause_between_calls_seconds: float = Field(default=0.0, ge=0)


class RunSection(_Section):
    runs: int = Field(default=3, ge=1)
    pause_between_runs_seconds: float = Field(default=5.0, ge=0)
    pause_between_messages_seconds: float = Field(default=2.0, ge=0)
    pause_between_cases_seconds: float = Field(default=10.0, ge=0)
    case_pass_rate: float = Field(default=0.67, gt=0.0, le=1.0)
    retry_on_error: int = Field(default=1, ge=0)
    retry_pause_seconds: float = Field(default=30.0, ge=0)
    output_dir: str = "reports/evaluation"
    console_log_level: Literal["DEBUG", "INFO", "WARNING"] = "INFO"


class KindSection(_Section):
    enabled: bool = True
    runs: int | None = Field(default=None, ge=1)
    pause_between_runs_seconds: float | None = Field(default=None, ge=0)
    pause_between_cases_seconds: float | None = Field(default=None, ge=0)
    skip_cases: list[str] = Field(default_factory=list)


class CapabilitySection(_Section):
    available: bool
    tools: list[str] = Field(default_factory=list)


class MarkersSection(_Section):
    plan_status: str = "Formulating a plan"
    tool_status_prefix: str = "Running "


class SecuritySection(_Section):
    instruction_markers: list[str] = Field(default_factory=list)
    secret_patterns: list[str] = Field(default_factory=list)

    @field_validator("secret_patterns")
    @classmethod
    def _compiles(cls, patterns: list[str]) -> list[str]:
        for pattern in patterns:
            re.compile(pattern)
        return patterns


class ControlPanel(_Section):
    agent: AgentSection
    judge: JudgeSection
    run: RunSection = Field(default_factory=RunSection)
    kinds: dict[Kind, KindSection] = Field(default_factory=dict)
    capabilities: dict[str, CapabilitySection] = Field(default_factory=dict)
    markers: MarkersSection = Field(default_factory=MarkersSection)
    security: SecuritySection = Field(default_factory=SecuritySection)

    def kind(self, kind: Kind) -> KindSection:
        return self.kinds.get(kind, KindSection())

    @classmethod
    def load(cls, path: Path) -> ControlPanel:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
        return cls.model_validate(_without_comments(raw))


def _without_comments(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_comments(item)
            for key, item in value.items()
            if not str(key).startswith("_")
        }
    if isinstance(value, list):
        return [_without_comments(item) for item in value]
    return value
