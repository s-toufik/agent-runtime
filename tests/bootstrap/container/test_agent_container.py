import asyncio
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import uvicorn
from a2a.server.tasks.database_task_store import DatabaseTaskStore
from pycraftcore.application_configuration.enum import ConnectorType
from pycraftcore.application_configuration.model import McpConnector
from pycraftcore.authentication.model.no_auth import NoAuth

from agent_runtime.adapter.inbound.web.stream.stream_agent_controller import (
    StreamAgentController,
)
from bootstrap.configuration.settings import ProcessSettings
from bootstrap.container.agent_container import AgentContainer
from tests.support.agents import TEST_AGENT, TEST_AGENTS
from tests.support.mcp_test_server import build_mcp_asgi_app, build_mcp_server

REAL_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"


def make_settings() -> ProcessSettings:
    return ProcessSettings(
        environment="debug",
        configuration_directory=REAL_CONFIG_DIR,
        agent=TEST_AGENT,
        agents_directory=TEST_AGENTS,
    )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@asynccontextmanager
async def serving_toolbox(port: int) -> AsyncIterator[str]:
    server = build_mcp_server(name="toolbox", version="1.0.0")

    @server.tool(name="echo", description="Echoes.")
    async def echo(text: str) -> str:
        return text

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


@pytest.fixture
async def running_toolbox() -> AsyncIterator[str]:
    async with serving_toolbox(_free_port()) as base_url:
        yield base_url


def test_is_not_ready_before_boot() -> None:
    container = AgentContainer(make_settings())

    assert container.is_ready is False


def test_logging_and_application_configuration_expose_the_di_internals() -> None:
    container = AgentContainer(make_settings())

    assert container.logging is container._logging
    assert container.application_configuration is container._configuration


def test_the_boot_time_services_exist_only_once_booted() -> None:
    container = AgentContainer(make_settings())

    for service in ("stream_agent_controller", "run_a2a_task", "a2a_task_store"):
        with pytest.raises(RuntimeError, match="not booted"):
            getattr(container, service)


def test_the_a2a_handler_and_card_exist_before_boot() -> None:
    container = AgentContainer(make_settings())

    assert container.a2a_request_handler is container.a2a_request_handler
    assert container.a2a_agent_card.name == container.agent.name == "assistant"


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
    assert isinstance(container.a2a_task_store, DatabaseTaskStore)
    assert (await container.list_models.handle()).models
    assert {task.get_name() for task in container._background} == {
        "mcp-tool-refresher",
        "a2a-task-retention",
    }

    await container.stop()

    assert container.is_ready is False
    assert container._background == []


async def test_stop_after_boot_does_not_raise(running_toolbox, monkeypatch) -> None:
    monkeypatch.setenv("TOOLBOX_URL", running_toolbox)
    container = AgentContainer(make_settings())
    await container.boot()

    await container.stop()


async def test_a_toolbox_that_starts_after_the_agent_gives_it_its_tools_without_a_restart(
    monkeypatch,
) -> None:
    port = _free_port()
    monkeypatch.setenv("TOOLBOX_URL", f"http://127.0.0.1:{port}/mcp")
    container = AgentContainer(make_settings())
    await container.boot()
    assert container.is_ready is True
    assert container._tools.registry.specifications() == []

    async with serving_toolbox(port):
        container._tools.refresher.wake()
        async with asyncio.timeout(15):
            while not container._tools.registry.specifications():
                await asyncio.sleep(0.05)

    assert [spec.name for spec in container._tools.registry.specifications()] == ["echo"]
    await container.stop()
