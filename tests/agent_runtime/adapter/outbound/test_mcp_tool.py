from typing import Any

from pycraftcore.mcp import CallResult, McpUnavailableException, RemoteTool

from agent_runtime.adapter.outbound.tool.mcp.mcp_tool import McpTool
from agent_runtime.adapter.outbound.tool.mcp.mcp_tool_provider import McpToolProvider
from agent_runtime.domain.exception.tool_unavailable_exception import ToolUnavailableException
from agent_runtime.domain.tool.tool_call import ToolCall
from agent_runtime.domain.tool.tool_context import ToolContext
from agent_runtime.domain.tool.tool_specification import ToolSpecification

SPEC = ToolSpecification(name="run_sql", description="SQL.", parameters={"type": "object"})
CONTEXT = ToolContext(conversation="conversation-1", model="m")


class FakeClient:
    def __init__(
        self,
        tools: list[RemoteTool] | None = None,
        result: CallResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self._tools = tools or []
        self._result = result
        self._error = error
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self) -> list[RemoteTool]:
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> CallResult:
        self.calls.append((name, arguments))
        if self._error:
            raise self._error
        assert self._result is not None
        return self._result


def test_specification_property_exposes_the_tool_specification() -> None:
    assert McpTool(FakeClient(), SPEC).specification is SPEC


async def test_a_call_sends_the_tool_name_and_arguments() -> None:
    client = FakeClient(result=CallResult(content=("ok",)))

    result = await McpTool(client, SPEC).invoke(
        ToolCall(id="1", name="run_sql", arguments={"query": "SELECT 1"}), CONTEXT
    )

    assert client.calls == [("run_sql", {"query": "SELECT 1"})]
    assert result.output == "ok"


async def test_an_unreachable_server_is_a_failed_call_naming_the_cause() -> None:
    client = FakeClient(error=McpUnavailableException("ConnectionError: refused"))

    result = await McpTool(client, SPEC).invoke(ToolCall(id="1", name="run_sql"), CONTEXT)

    assert result.error == "MCP call failed: ConnectionError: refused"


async def test_structured_content_that_is_not_json_falls_back_to_the_text() -> None:
    client = FakeClient(result=CallResult(content=("a set",), structured={"rows": {1}}))

    result = await McpTool(client, SPEC).invoke(ToolCall(id="1", name="run_sql"), CONTEXT)

    assert result.output == "a set"


async def test_the_provider_turns_each_remote_tool_into_a_specification() -> None:
    remote = RemoteTool("echo", "Echoes.", {"type": "object"}, {"type": "object"})

    [tool] = await McpToolProvider(FakeClient([remote])).tools()

    assert tool.specification == ToolSpecification(
        name="echo",
        description="Echoes.",
        parameters={"type": "object"},
        output_schema={"type": "object"},
    )


async def test_a_required_provider_refuses_a_server_without_tools() -> None:
    try:
        await McpToolProvider(FakeClient()).tools()
    except ToolUnavailableException as exception:
        assert str(exception) == "The MCP server advertised no tool"
    else:
        raise AssertionError("an empty server was accepted")


async def test_an_optional_provider_accepts_a_server_without_tools() -> None:
    assert await McpToolProvider(FakeClient(), required=False).tools() == []
