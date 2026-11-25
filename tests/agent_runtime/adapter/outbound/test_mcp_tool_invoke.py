import asyncio
import socket
from collections.abc import AsyncIterator

import pytest
import uvicorn
from mcp.server.mcpserver.exceptions import ToolError
from opentelemetry import trace
from opentelemetry.trace import SpanKind
from pycraftcore.application_configuration.enum import ConnectorType
from pycraftcore.application_configuration.model import McpConnector
from pycraftcore.authentication.model.no_auth import NoAuth
from pycraftcore.mcp_sdk import SdkMcpClient
from pydantic import BaseModel

from agent_runtime.adapter.outbound.tool.mcp.mcp_tool import McpTool
from agent_runtime.adapter.outbound.tool.mcp.mcp_tool_provider import McpToolProvider
from agent_runtime.domain.tool.tool_call import ToolCall
from agent_runtime.domain.tool.tool_context import ToolContext
from agent_runtime.domain.tool.tool_specification import ToolSpecification
from tests.support.mcp_test_server import build_mcp_asgi_app, build_mcp_server
from tests.support.tracing import is_child_of


class Rows(BaseModel):
    rows: list[dict[str, int]]


CONTEXT = ToolContext(conversation="conversation-1", model="m")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
async def running_server() -> AsyncIterator[str]:
    server = build_mcp_server(name="toolbox", version="1.0.0")

    @server.tool(name="structured", description="Returns structured content.")
    async def structured() -> Rows:
        return Rows(rows=[{"n": 1}])

    @server.tool(
        name="unstructured", description="Returns plain text only.", structured_output=False
    )
    async def unstructured() -> str:
        return "plain text"

    @server.tool(name="add", description="Add.")
    async def add(a: int, b: int) -> int:
        return a + b

    @server.tool(name="always_fails", description="Always fails.")
    async def always_fails() -> str:
        raise ToolError("boom")

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


def _client(base_url: str, logger) -> SdkMcpClient:
    connector = McpConnector(
        name="self",
        type=ConnectorType.mcp,
        auth=NoAuth(),
        base_url=base_url,
        timeout=5,
        transport="streamable_http",
    )
    return SdkMcpClient(connector, logger=logger)


def _tool(base_url: str, name: str, logger) -> McpTool:
    return McpTool(_client(base_url, logger), ToolSpecification(name=name, description="."))


async def test_provider_carries_each_tools_input_and_output_schema(running_server, logger) -> None:
    tools = await McpToolProvider(_client(running_server, logger)).tools()
    specifications = {tool.specification.name: tool.specification for tool in tools}

    assert specifications["structured"].parameters["type"] == "object"
    assert specifications["structured"].output_schema == Rows.model_json_schema()
    assert specifications["unstructured"].output_schema is None


async def test_prefers_structured_content_when_present(running_server, logger) -> None:
    tool = _tool(running_server, "structured", logger)

    result = await tool.invoke(ToolCall(id="1", name="structured"), CONTEXT)

    assert not result.error
    assert result.output == '{"rows": [{"n": 1}]}'


async def test_falls_back_to_text_when_no_structured_content(running_server, logger) -> None:
    tool = _tool(running_server, "unstructured", logger)

    result = await tool.invoke(ToolCall(id="1", name="unstructured"), CONTEXT)

    assert not result.error
    assert result.output == "plain text"


async def test_failure_still_reads_the_text_error_message(running_server, logger) -> None:
    tool = _tool(running_server, "always_fails", logger)

    result = await tool.invoke(ToolCall(id="1", name="always_fails"), CONTEXT)

    assert result.error
    assert "boom" in result.error


async def test_a_tool_call_joins_the_trace_of_the_step_that_made_it(
    running_server, logger, spans
) -> None:
    tool = _tool(running_server, "add", logger)

    with trace.get_tracer("test").start_as_current_span("agent run_tools") as step:
        result = await tool.invoke(
            ToolCall(id="c1", name="add", arguments={"a": 1, "b": 2}), CONTEXT
        )

    assert result.error is None
    named = {(span.name, span.kind): span for span in spans.get_finished_spans()}
    sent = named["MCP send tools/call add", SpanKind.CLIENT]
    served = named["tools/call add", SpanKind.SERVER]
    assert is_child_of(sent, step)
    assert served.context is not None
    assert served.context.trace_id == step.get_span_context().trace_id
