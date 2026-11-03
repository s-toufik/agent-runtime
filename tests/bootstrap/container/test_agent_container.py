import asyncio
import socket
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import uvicorn
from pycraftcore.application_configuration.enum import ConnectorType
from pycraftcore.application_configuration.model.connector import McpConnector
from pycraftcore.authentication.model.no_auth import NoAuth

from agent_runtime.adapter.inbound.web.stream.stream_agent_controller import (
    StreamAgentController,
)
from bootstrap.configuration.settings import ProcessSettings
from bootstrap.container.agent_container import AgentContainer
from tests.support.mcp_test_server import build_mcp_asgi_app, build_mcp_server

REAL_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"


@pytest.fixture(autouse=True)
def _base_env(monkeypatch, tmp_path):
    monkeypatch.setenv("OTEL_HOST", "")
    monkeypatch.setenv("OTEL_PORT", "4317")
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


def make_settings() -> ProcessSettings:
    return ProcessSettings(
        role="agent-runtime",
        environment="debug",
        configuration_directory=REAL_CONFIG_DIR,
    )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
async def running_toolbox() -> AsyncIterator[str]:
    server = build_mcp_server(name="toolbox", version="1.0.0")

    @server.tool(name="echo", description="Echoes.")
    async def echo(text: str) -> str:
        return text

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}/mcp"
    connector = McpConnector(
        name="self",
        type=ConnectorType.mcp,
        auth=NoAuth(),
        base_url=base_url,
        timeout=5,
        transport="streamable_http",
    )
    app = build_mcp_asgi_app(server, connector)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    uv_server = uvicorn.Server(config)
    serve_task = asyncio.create_task(uv_server.serve())
    try:
        while not uv_server.started:
            await asyncio.sleep(0.01)
        yield base_url
    finally:
        uv_server.should_exit = True
        await serve_task


def test_is_not_ready_before_boot() -> None:
    container = AgentContainer(make_settings())

    assert container.is_ready is False


def test_logging_and_application_configuration_expose_the_di_internals() -> None:
    container = AgentContainer(make_settings())

    assert container.logging is container._logging
    assert container.application_configuration is container._configuration


def test_the_stream_controller_exists_only_once_booted() -> None:
    container = AgentContainer(make_settings())

    with pytest.raises(RuntimeError, match="not booted"):
        _ = container.stream_agent_controller


def test_the_actuator_reports_the_readiness_of_the_container() -> None:
    container = AgentContainer(make_settings())

    assert container.actuator.readiness().status_code == 503
    container._ready = True
    assert container.actuator.readiness().status_code == 200


async def test_boot_builds_the_stream_controller_and_becomes_ready(
    running_toolbox, monkeypatch
) -> None:
    monkeypatch.setenv("TOOLBOX_URL", running_toolbox)
    container = AgentContainer(make_settings())

    await container.boot()

    assert container.is_ready is True
    assert isinstance(container.stream_agent_controller, StreamAgentController)
    assert (await container.list_models.handle()).models

    await container.stop()

    assert container.is_ready is False


async def test_stop_after_boot_does_not_raise(running_toolbox, monkeypatch) -> None:
    monkeypatch.setenv("TOOLBOX_URL", running_toolbox)
    container = AgentContainer(make_settings())
    await container.boot()

    await container.stop()
