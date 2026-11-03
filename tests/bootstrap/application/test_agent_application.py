from pathlib import Path

import pytest
from pycraftcore.web.asgi import ASGIApp

from bootstrap.application.agent_application import create_agent_application
from bootstrap.configuration.settings import ProcessSettings
from bootstrap.container.agent_container import AgentContainer
from tests.support.web import http_client, starts

REAL_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"


@pytest.fixture(autouse=True)
def _base_env(monkeypatch, tmp_path):
    monkeypatch.setenv("USER_DB_HOST", str(tmp_path))
    monkeypatch.setenv("USER_DB_NAME", "users")
    monkeypatch.setenv("DB_SQLITE_CHECKPOINT_HOST", str(tmp_path))
    monkeypatch.setenv("DB_SQLITE_CHECKPOINT_NAME", "checkpoint")
    monkeypatch.setenv("DB_MONGO_CHECKPOINT_HOST", "localhost")
    monkeypatch.setenv("DB_MONGO_CHECKPOINT_PORT", "27017")
    monkeypatch.setenv("DB_MONGO_CHECKPOINT_NAME", "checkpoint")
    monkeypatch.setenv("DB_MONGO_CHECKPOINT_USERNAME", "test")
    monkeypatch.setenv("DB_MONGO_CHECKPOINT_PASSWORD", "test")
    monkeypatch.setenv("LLM_API_KEY", "test")


@pytest.fixture
def booted(monkeypatch) -> None:
    async def fake_boot(self) -> None:
        self._ready = True

    async def fake_stop(self) -> None:
        self._ready = False

    monkeypatch.setattr(AgentContainer, "boot", fake_boot)
    monkeypatch.setattr(AgentContainer, "stop", fake_stop)


def create_app(monkeypatch, base_path: str = "", docs: bool = False) -> ASGIApp:
    monkeypatch.setenv("WEB_BASE_PATH", base_path)
    monkeypatch.setenv("WEB_DOCS", str(docs).lower())
    settings = ProcessSettings(
        role="agent-runtime", environment="debug", configuration_directory=REAL_CONFIG_DIR
    )
    return create_agent_application(settings=settings)


async def test_a_booted_api_reports_healthy_and_lists_the_configured_models(
    monkeypatch, booted
) -> None:
    async with http_client(create_app(monkeypatch)) as client:
        health = await client.get("/actuator/health")
        readiness = await client.get("/actuator/health/readiness")
        models = await client.get("/v1/models")

    assert (health.status_code, health.json()) == (200, {"status": "UP"})
    assert (readiness.status_code, readiness.json()) == (200, {"status": "UP"})
    assert models.status_code == 200
    assert models.json()["models"]


async def test_the_api_is_served_under_the_base_path(monkeypatch, booted) -> None:
    async with http_client(create_app(monkeypatch, base_path="/agent-runtime")) as client:
        prefixed = await client.get("/agent-runtime/actuator/health")
        bare = await client.get("/actuator/health")

    assert (prefixed.status_code, bare.status_code) == (200, 404)


async def test_the_api_documentation_is_off_unless_web_docs_is_true(monkeypatch, booted) -> None:
    async with http_client(create_app(monkeypatch)) as client:
        hidden = await client.get("/docs")
    async with http_client(create_app(monkeypatch, docs=True)) as client:
        ui = await client.get("/docs", follow_redirects=True)
        schema = await client.get("/docs/openapi.json")

    assert hidden.status_code == 404
    assert ui.status_code == 200
    assert schema.json()["info"]["title"] == "agent-runtime"
    assert {"/v1/stream", "/v1/models", "/actuator/health"} <= set(schema.json()["paths"])


async def test_the_api_documentation_follows_the_base_path(monkeypatch, booted) -> None:
    app = create_app(monkeypatch, base_path="/agent-runtime", docs=True)

    async with http_client(app) as client:
        schema = await client.get("/agent-runtime/docs/openapi.json")

    assert "/agent-runtime/v1/stream" in schema.json()["paths"]


async def test_each_route_is_logged_at_startup(monkeypatch, booted, caplog) -> None:
    async with http_client(create_app(monkeypatch)):
        pass

    assert "Route POST /v1/stream included" in caplog.text
    assert "Route GET /v1/models included" in caplog.text


async def test_a_boot_failure_stops_the_startup_and_is_logged(monkeypatch, caplog) -> None:
    async def failing_boot(self) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(AgentContainer, "boot", failing_boot)

    assert await starts(create_app(monkeypatch)) is False
    assert "Agent container failed to boot" in caplog.text
    assert "boom" in caplog.text
