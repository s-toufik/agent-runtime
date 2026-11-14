from pathlib import Path

import pytest

from bootstrap.configuration.settings import ProcessSettings
from bootstrap.di.agent_di import AgentDI

REAL_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"


@pytest.fixture(autouse=True)
def _base_env(monkeypatch, tmp_path):
    monkeypatch.setenv("OTEL_HOST", "")
    monkeypatch.setenv("OTEL_PORT", "4317")
    monkeypatch.setenv("TOOLBOX_URL", "http://localhost:8001/mcp")
    monkeypatch.setenv("USER_DB_HOST", str(tmp_path))
    monkeypatch.setenv("USER_DB_NAME", "users")
    monkeypatch.setenv("DB_SQLITE_CHECKPOINT_HOST", str(tmp_path))
    monkeypatch.setenv("DB_SQLITE_CHECKPOINT_NAME", "checkpoint")
    monkeypatch.setenv("DB_MONGO_CHECKPOINT_HOST", "localhost")
    monkeypatch.setenv("DB_MONGO_CHECKPOINT_PORT", "27017")
    monkeypatch.setenv("DB_MONGO_CHECKPOINT_NAME", "checkpoint")
    monkeypatch.setenv("DB_MONGO_CHECKPOINT_USERNAME", "test")
    monkeypatch.setenv("DB_MONGO_CHECKPOINT_PASSWORD", "test")
    monkeypatch.setenv("DB_POSTGRES_A2A_HOST", "")
    monkeypatch.setenv("HOMELAB_LLM_BASE_URL", "http://llm:8080/v1")
    monkeypatch.setenv("NVIDIA_LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
    monkeypatch.setenv("NVIDIA_LLM_API_KEY", "test")


def make_settings(guardrail_enabled: bool = False) -> ProcessSettings:
    return ProcessSettings(
        role="agent-runtime",
        environment="debug",
        configuration_directory=REAL_CONFIG_DIR,
        guardrail_enabled=guardrail_enabled,
    )


@pytest.fixture
def di() -> AgentDI:
    return AgentDI(make_settings())
