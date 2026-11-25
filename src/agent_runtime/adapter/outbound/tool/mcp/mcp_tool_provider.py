from pycraftcore.mcp import McpClient, RemoteTool

from agent_runtime.adapter.outbound.tool.mcp.mcp_tool import McpTool
from agent_runtime.application.port.outbound.tool_provider import ToolPort
from agent_runtime.domain.exception.tool_unavailable_exception import ToolUnavailableException
from agent_runtime.domain.tool.tool_specification import ToolSpecification


class McpToolProvider:
    def __init__(self, client: McpClient, required: bool = True) -> None:
        self._client = client
        self._required = required

    async def tools(self) -> list[ToolPort]:
        remotes: list[RemoteTool] = await self._client.list_tools()
        tools: list[ToolPort] = [
            McpTool(
                self._client,
                ToolSpecification(
                    name=remote.name,
                    description=remote.description,
                    parameters=remote.input_schema or {},
                    output_schema=remote.output_schema,
                ),
            )
            for remote in remotes
        ]
        if self._required and not tools:
            raise ToolUnavailableException("The MCP server advertised no tool")
        return tools
