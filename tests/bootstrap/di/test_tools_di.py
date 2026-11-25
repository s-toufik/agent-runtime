from dataclasses import replace
from pathlib import Path

from pycraftcore.application_configuration import ApplicationConfiguration
from pycraftcore.application_configuration.enum import (
    ConnectorType,
    OperationType,
    RunTypeEnvironment,
)
from pycraftcore.application_configuration.enum.run_type_application import RunTypeApplication
from pycraftcore.application_configuration.model import (
    ConnectorRegistry,
    ConnectorTyping,
    McpConnector,
    McpOperation,
    McpRefresh,
    OperationRegistry,
    ServerRegistry,
)
from pycraftcore.authentication.model.no_auth import NoAuth
from pycraftcore.logger.enum import LogLevel
from pycraftcore.mcp import McpUnavailableException, RemoteTool

from agent_runtime.domain.agent.tool_scope import ToolScope
from bootstrap.di.agent_di import AgentDI
from bootstrap.di.tools_di import EXTERNAL_MCP_PREFIX, MCP_CONNECTOR_NAME, ToolsDI
from tests.bootstrap.di.conftest import make_settings

REAL_AGENTS = Path(__file__).resolve().parents[3] / "agents"


def _connector(name: str, base_url: str) -> McpConnector:
    return McpConnector(
        name=name,
        type=ConnectorType.mcp,
        auth=NoAuth(),
        base_url=base_url,
        timeout=5,
        transport="streamable_http",
    )


def _tools(
    logger,
    scope: ToolScope | None = None,
    operations: tuple[McpOperation, ...] = (),
    **mcp_connectors: McpConnector,
) -> ToolsDI:
    by_type: dict[str, ConnectorTyping] = dict(mcp_connectors)
    configuration = ApplicationConfiguration(
        env=RunTypeEnvironment.debug,
        run=RunTypeApplication.asynchronous,
        log=LogLevel.INFO,
        server=ServerRegistry(),
        connector=ConnectorRegistry({ConnectorType.mcp: by_type}),
        operation=OperationRegistry({operation.name: operation for operation in operations}),
    )
    return ToolsDI(configuration, logger, scope)


TOOLBOX = {MCP_CONNECTOR_NAME: _connector("toolbox", "http://localhost:8001/mcp")}


def test_the_default_toolbox_connector_is_always_used(logger) -> None:
    assert set(_tools(logger, **TOOLBOX).clients) == {"toolbox"}


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

    assert set(tools.clients) == {
        "toolbox",
        f"{EXTERNAL_MCP_PREFIX}analytics",
        f"{EXTERNAL_MCP_PREFIX}billing",
    }


def test_each_mcp_server_is_refreshed_at_the_pace_its_connector_sets(logger) -> None:
    toolbox = _connector("toolbox", "http://localhost:8001/mcp")
    toolbox.refresh = McpRefresh(interval=120, retry_delay=2, max_retry_delay=30)

    [source] = _tools(logger, **{MCP_CONNECTOR_NAME: toolbox}).refresher._sources

    assert source.name == "toolbox"
    assert source.policy == McpRefresh(interval=120, retry_delay=2, max_retry_delay=30)


def test_the_headers_of_a_connector_s_mcp_operation_reach_its_client(logger) -> None:
    toolbox = _connector("toolbox", "http://localhost:8001/mcp")
    operation = McpOperation(
        name="toolbox_calls",
        type=OperationType.mcp,
        connector=toolbox,
        headers={"X-Team": "kitchen"},
    )

    tools = _tools(logger, operations=(operation,), **{MCP_CONNECTOR_NAME: toolbox})

    assert tools.clients["toolbox"]._headers() == {"X-Team": "kitchen"}


async def test_close_is_a_no_op_when_nothing_was_built(logger) -> None:
    await _tools(logger, **TOOLBOX).close()


class _FakeMcpClient:
    def __init__(self, tools: list[RemoteTool]) -> None:
        self._tools = tools

    async def list_tools(self) -> list[RemoteTool]:
        return self._tools


class _UnreachableMcpClient:
    async def list_tools(self) -> list[RemoteTool]:
        raise McpUnavailableException("connection refused")


ECHO = RemoteTool("echo", "Echoes.", {"type": "object"})


def _with_clients(logger, clients: dict) -> ToolsDI:
    connectors = {name: _connector(name, f"http://localhost:9000/{name}") for name in clients}
    tools = _tools(logger, **connectors)
    tools.__dict__["clients"] = clients
    return tools


async def test_the_toolbox_discovers_tools_from_the_mcp_server(logger) -> None:
    tools = _with_clients(logger, {"toolbox": _FakeMcpClient([ECHO])})

    toolbox = await tools.toolbox()

    assert [spec.name for spec in toolbox.tools()] == ["echo"]


async def test_the_toolbox_skips_servers_that_are_down_or_advertise_nothing(logger) -> None:
    tools = _with_clients(
        logger,
        {
            "toolbox": _UnreachableMcpClient(),
            f"{EXTERNAL_MCP_PREFIX}empty": _FakeMcpClient([]),
            f"{EXTERNAL_MCP_PREFIX}analytics": _FakeMcpClient([ECHO]),
        },
    )

    toolbox = await tools.toolbox()

    assert [spec.name for spec in toolbox.tools()] == ["echo"]


async def test_the_toolbox_is_empty_but_usable_when_no_server_answers(logger) -> None:
    tools = _with_clients(logger, {"toolbox": _UnreachableMcpClient()})

    toolbox = await tools.toolbox()

    assert toolbox.tools() == []
    assert any("No MCP tools available yet" in line for line in logger.messages("warning"))


def test_an_agent_reaches_the_toolbox_endpoint_of_its_scope(logger) -> None:
    observation = _tools(logger, ToolScope("observation"), **TOOLBOX)
    everything = _tools(logger, ToolScope("all"), **TOOLBOX)

    assert observation.connectors["toolbox"].base_url == "http://localhost:8001/mcp/observation"
    assert everything.connectors["toolbox"].base_url == "http://localhost:8001/mcp"


def test_an_agent_without_a_tool_scope_skips_the_toolbox_but_keeps_other_mcp_servers(
    logger,
) -> None:
    tools = _tools(
        logger,
        ToolScope("none"),
        **TOOLBOX,
        **{f"{EXTERNAL_MCP_PREFIX}billing": _connector("billing", "http://localhost:9002/mcp")},
    )

    assert set(tools.connectors) == {f"{EXTERNAL_MCP_PREFIX}billing"}


async def test_an_agent_without_a_tool_scope_says_so_instead_of_warning(logger) -> None:
    tools = _tools(logger, ToolScope("none"), **TOOLBOX)

    await tools.toolbox()

    assert logger.messages("warning") == []
    assert any("tool scope is 'none'" in message for message in logger.messages("info"))


def test_the_supervisor_asks_the_agents_that_have_a_url(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_OBSERVATION_URL", "http://agent-observation:8000")
    di = AgentDI(replace(make_settings(), agent="supervisor", agents_directory=REAL_AGENTS))

    tools = di._tools

    assert tools.peer_agents.names == ("observation",)
    assert [source.name for source in tools.refresher._sources][-1] == "agents"


def test_an_agent_without_peers_asks_nobody(logger) -> None:
    assert _tools(logger, **TOOLBOX)._peer_sources() == []
