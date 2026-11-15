from pathlib import Path

import pytest

REQUIRED: dict[str, str] = {
    "TOOLBOX_URL": "http://127.0.0.1:9/mcp",
    "DB_MONGO_CHECKPOINT_HOST": "localhost",
    "DB_MONGO_CHECKPOINT_PORT": "27017",
    "DB_MONGO_CHECKPOINT_NAME": "checkpoint",
    "DB_MONGO_CHECKPOINT_USERNAME": "test",
    "DB_MONGO_CHECKPOINT_PASSWORD": "test",
    "DB_SQLITE_CHECKPOINT_NAME": "checkpoint",
    "DB_POSTGRES_A2A_HOST": "",
    "DB_POSTGRES_A2A_PORT": "5432",
    "DB_POSTGRES_A2A_NAME": "agent_runtime",
    "DB_POSTGRES_A2A_USERNAME": "test",
    "DB_POSTGRES_A2A_PASSWORD": "test",
    "HOMELAB_LLM_BASE_URL": "http://llm:8080/v1",
    "NVIDIA_LLM_BASE_URL": "https://integrate.api.nvidia.com/v1",
    "NVIDIA_LLM_API_KEY": "test",
    "OTEL_HOST": "",
    "OTEL_PORT": "4317",
}

DEFAULTED: tuple[str, ...] = (
    "APP_ENV",
    "AGENT",
    "AGENTS_DIR",
    "CONFIGURATION_DIR",
    "LOG_LEVEL",
    "WEB_BASE_PATH",
    "WEB_DOCS",
    "GUARDRAIL_ENABLED",
    "MAX_CONCURRENT_STREAMS",
    "AGENT_ANSWER_DELIVERY",
    "A2A_MODEL",
    "A2A_URL",
    "A2A_TASK_TTL",
    "A2A_TASKS_TABLE",
    "HOMELAB_LLM_API_KEY",
    "MCP_REFRESH_INTERVAL",
    "MCP_RETRY_DELAY",
    "MCP_MAX_RETRY_DELAY",
)


def apply_test_environment(monkeypatch: pytest.MonkeyPatch, sqlite_directory: Path) -> None:
    for key in DEFAULTED:
        monkeypatch.delenv(key, raising=False)
    for key, value in REQUIRED.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("DB_SQLITE_CHECKPOINT_HOST", str(sqlite_directory))
