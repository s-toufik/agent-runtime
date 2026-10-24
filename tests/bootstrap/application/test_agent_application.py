from pathlib import Path

import pytest
from pycraftcore.web.asgi import ASGIApp
from pycraftcore.web.enum import WebFramework
from pycraftcore.web.schema import HttpRoute

from bootstrap.application.agent_application import create_agent_application
from bootstrap.configuration.settings import ProcessSettings
from bootstrap.container.agent_container import AgentContainer
from tests.support.web import EVERY_FRAMEWORK, http_client, starts

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


def create_app(
    monkeypatch, framework: WebFramework, base_path: str = "", docs: bool = False
) -> ASGIApp:
    monkeypatch.setenv("WEB_FRAMEWORK", framework)
    monkeypatch.setenv("WEB_BASE_PATH", base_path)
    monkeypatch.setenv("WEB_DOCS", str(docs).lower())
    settings = ProcessSettings(
        role="agent-runtime", environment="debug", configuration_directory=REAL_CONFIG_DIR
    )
    return create_agent_application(settings=settings)


def fake_container(monkeypatch) -> None:
    async def fake_boot(self) -> None:
        self._routes.extend(self._actuator_routes())
        self._ready = True

    async def fake_stop(self) -> None:
        self._ready = False

    monkeypatch.setattr(AgentContainer, "boot", fake_boot)
    monkeypatch.setattr(AgentContainer, "stop", fake_stop)


@EVERY_FRAMEWORK
async def test_full_lifespan_includes_the_booted_routes_and_reports_healthy(
    monkeypatch, framework
) -> None:
    async def ping() -> dict:
        return {"pong": True}

    async def fake_boot(self) -> None:
        self._routes.append(HttpRoute("GET", "/fake/ping", ping))
        self._routes.extend(self._actuator_routes())
        self._ready = True

    async def fake_stop(self) -> None:
        self._ready = False

    monkeypatch.setattr(AgentContainer, "boot", fake_boot)
    monkeypatch.setattr(AgentContainer, "stop", fake_stop)
    app = create_app(monkeypatch, framework)

    async with http_client(app) as client:
        health = await client.get("/actuator/health")
        readiness = await client.get("/actuator/health/readiness")
        fake = await client.get("/fake/ping")

    assert health.status_code == 200
    assert health.json() == {"status": "UP"}
    assert readiness.status_code == 200
    assert readiness.json() == {"status": "UP"}
    assert fake.status_code == 200
    assert fake.json() == {"pong": True}


@EVERY_FRAMEWORK
async def test_the_api_is_served_under_the_base_path(monkeypatch, framework) -> None:
    fake_container(monkeypatch)
    app = create_app(monkeypatch, framework, base_path="/agent-runtime")

    async with http_client(app) as client:
        prefixed = await client.get("/agent-runtime/actuator/health")
        bare = await client.get("/actuator/health")

    assert prefixed.status_code == 200
    assert bare.status_code == 404


@EVERY_FRAMEWORK
async def test_the_api_documentation_is_off_unless_web_docs_is_true(monkeypatch, framework) -> None:
    fake_container(monkeypatch)

    async with http_client(create_app(monkeypatch, framework)) as client:
        hidden = await client.get("/docs")
    async with http_client(create_app(monkeypatch, framework, docs=True)) as client:
        ui = await client.get("/docs")
        schema = await client.get("/docs/openapi.json")

    assert hidden.status_code == 404
    assert ui.status_code == 200
    assert schema.json()["info"]["title"] == "agent-runtime"
    assert "/actuator/health" in schema.json()["paths"]


@EVERY_FRAMEWORK
async def test_the_api_documentation_follows_the_base_path(monkeypatch, framework) -> None:
    fake_container(monkeypatch)
    app = create_app(monkeypatch, framework, base_path="/agent-runtime", docs=True)

    async with http_client(app) as client:
        schema = await client.get("/agent-runtime/docs/openapi.json")

    assert "/agent-runtime/actuator/health" in schema.json()["paths"]


@EVERY_FRAMEWORK
async def test_a_boot_failure_stops_the_startup_and_is_logged(
    monkeypatch, framework, caplog
) -> None:
    async def failing_boot(self) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(AgentContainer, "boot", failing_boot)
    app = create_app(monkeypatch, framework)

    assert await starts(app) is False
    assert "Agent container failed to boot" in caplog.text
    assert "boom" in caplog.text
