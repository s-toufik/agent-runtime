from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pycraftcore.application_configuration import ApplicationConfiguration
from pycraftcore.application_configuration.enum import ConnectorType, RunTypeEnvironment
from pycraftcore.application_configuration.enum.run_type_application import RunTypeApplication
from pycraftcore.application_configuration.model.connector import (
    ConnectorRegistry,
    ConnectorTyping,
    McpConnector,
    McpRefresh,
)
from pycraftcore.application_configuration.model.operation import OperationRegistry
from pycraftcore.application_configuration.model.server import ServerRegistry
from pycraftcore.authentication.model.no_auth import NoAuth
from pycraftcore.logger.enum import LogLevel

from agent_runtime.domain.tool.refresh_policy import RefreshPolicy
from bootstrap.di.tools_di import EXTERNAL_MCP_PREFIX, MCP_CONNECTOR_NAME, ToolsDI


def _connector(name: str, base_url: str) -> McpConnector:
    return McpConnector(
        name=name,
        type=ConnectorType.mcp,
        auth=NoAuth(),
        base_url=base_url,
        timeout=5,
        transport="streamable_http",
    )


def _tools(logger, **mcp_connectors: McpConnector) -> ToolsDI:
    by_type: dict[str, ConnectorTyping] = dict(mcp_connectors)
    configuration = ApplicationConfiguration(
        env=RunTypeEnvironment.debug,
        run=RunTypeApplication.asynchronous,
        log=LogLevel.INFO,
        server=ServerRegistry(),
        connector=ConnectorRegistry({ConnectorType.mcp: by_type}),
        operation=OperationRegistry({}),
    )
    return ToolsDI(configuration, logger)


TOOLBOX = {MCP_CONNECTOR_NAME: _connector("toolbox", "http://localhost:8001/mcp")}


def test_the_default_toolbox_connector_is_always_used(logger) -> None:
    assert set(_tools(logger, **TOOLBOX).session_factories) == {"toolbox"}


def test_every_external_mcp_prefixed_connector_is_merged_in(logger) -> None:
    tools = _tools(
        logger,
        **TOOLBOX,
        **{
            f"{EXTERNAL_MCP_PREFIX}analytics": _connector("analytics", "http://localhost:9001/mcp"),
            f"{EXTERNAL_MCP_PREFIX}billing": _connector("billing", "http://localhost:9002/mcp"),
            "unrelated_other_connector": _connector("other", "http://localhost:9003/mcp"),
        },
    )

    assert set(tools.session_factories) == {
        "toolbox",
        f"{EXTERNAL_MCP_PREFIX}analytics",
        f"{EXTERNAL_MCP_PREFIX}billing",
    }


def test_each_mcp_server_is_refreshed_at_the_pace_its_connector_sets(logger) -> None:
    toolbox = _connector("toolbox", "http://localhost:8001/mcp")
    toolbox.refresh = McpRefresh(interval=120, retry_delay=2, max_retry_delay=30)

    [source] = _tools(logger, **{MCP_CONNECTOR_NAME: toolbox}).refresher._sources

    assert source.name == "toolbox"
    assert source.policy == RefreshPolicy(interval=120, retry_delay=2, max_retry_delay=30)


async def test_close_is_a_no_op_when_nothing_was_built(logger) -> None:
    await _tools(logger, **TOOLBOX).close()


class _FakeMcpSession:
    def __init__(self, tools: list) -> None:
        self._tools = tools

    async def list_tools(self):
        class Response:
            tools = self._tools

        return Response()


class _FakeMcpSessionFactory:
    def __init__(self, tools: list) -> None:
        self._tools = tools

    @asynccontextmanager
    async def session(self) -> AsyncIterator[_FakeMcpSession]:
        yield _FakeMcpSession(self._tools)


class _UnreachableMcpSessionFactory:
    @asynccontextmanager
    async def session(self) -> AsyncIterator[_FakeMcpSession]:
        raise ConnectionError("connection refused")
        yield  # pragma: no cover


class _AdvertisedTool:
    def __init__(self, name: str, description: str, input_schema: dict) -> None:
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.output_schema = None


ECHO = _AdvertisedTool("echo", "Echoes.", {"type": "object"})


def _with_sessions(logger, sessions: dict) -> ToolsDI:
    tools = _tools(logger, **TOOLBOX)
    tools.__dict__["session_factories"] = sessions
    return tools


async def test_the_toolbox_discovers_tools_from_the_mcp_server(logger) -> None:
    tools = _with_sessions(logger, {"toolbox": _FakeMcpSessionFactory([ECHO])})

    toolbox = await tools.toolbox()

    assert [spec.name for spec in toolbox.tools()] == ["echo"]


async def test_the_toolbox_skips_servers_that_are_down_or_advertise_nothing(logger) -> None:
    tools = _with_sessions(
        logger,
        {
            "toolbox": _UnreachableMcpSessionFactory(),
            f"{EXTERNAL_MCP_PREFIX}empty": _FakeMcpSessionFactory([]),
            f"{EXTERNAL_MCP_PREFIX}analytics": _FakeMcpSessionFactory([ECHO]),
        },
    )

    toolbox = await tools.toolbox()

    assert [spec.name for spec in toolbox.tools()] == ["echo"]


async def test_the_toolbox_is_empty_but_usable_when_no_server_answers(logger) -> None:
    tools = _with_sessions(logger, {"toolbox": _UnreachableMcpSessionFactory()})

    toolbox = await tools.toolbox()

    assert toolbox.tools() == []
    assert any("No MCP tools available yet" in line for line in logger.messages("warning"))
