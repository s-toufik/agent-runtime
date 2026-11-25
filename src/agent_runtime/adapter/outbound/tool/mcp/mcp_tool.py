import json

from pycraftcore.mcp import CallResult, McpClient, McpUnavailableException

from agent_runtime.domain.tool.tool_call import ToolCall
from agent_runtime.domain.tool.tool_context import ToolContext
from agent_runtime.domain.tool.tool_result import ToolResult
from agent_runtime.domain.tool.tool_specification import ToolSpecification


class McpTool:
    def __init__(self, client: McpClient, specification: ToolSpecification) -> None:
        self._client = client
        self._specification = specification

    @property
    def specification(self) -> ToolSpecification:
        return self._specification

    async def invoke(self, call: ToolCall, context: ToolContext) -> ToolResult:
        try:
            result: CallResult = await self._client.call_tool(
                self._specification.name, call.arguments
            )
        except McpUnavailableException as exception:
            return ToolResult.failure(
                call_id=call.id,
                tool_name=self._specification.name,
                error=f"MCP call failed: {exception}",
            )
        if result.is_error:
            return ToolResult.failure(
                call_id=call.id, tool_name=self._specification.name, error=result.text
            )
        return ToolResult(
            call_id=call.id, tool_name=self._specification.name, output=self._rendered(result)
        )

    @staticmethod
    def _rendered(result: CallResult) -> str:
        if result.structured is not None:
            try:
                return json.dumps(result.structured)
            except TypeError, ValueError:
                pass
        return result.text
