from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp import Client, ClientSession
from mcp.server.mcpserver import MCPServer
from opentelemetry import trace

from agent_runtime.adapter.outbound.tool.mcp.mcp_tool import McpTool
from agent_runtime.domain.tool.tool_call import ToolCall
from agent_runtime.domain.tool.tool_specification import ToolSpecification
from tests.support.tracing import by_name

server = MCPServer("toolbox")


@server.tool()
def add(a: int, b: int) -> int:
    return a + b


class InMemorySessions:
    @asynccontextmanager
    async def session(self) -> AsyncIterator[ClientSession]:
        async with Client(server) as client:
            yield client.session


async def test_a_tool_call_joins_the_trace_of_the_step_that_made_it(spans) -> None:
    tool = McpTool(InMemorySessions(), ToolSpecification(name="add", description="Add."))

    with trace.get_tracer("test").start_as_current_span("agent run_tools") as step:
        result = await tool.invoke(ToolCall(id="c1", name="add", arguments={"a": 1, "b": 2}))

    assert result.error is None
    call = by_name(spans)["tools/call add"]
    assert call.context is not None
    assert call.context.trace_id == step.get_span_context().trace_id
