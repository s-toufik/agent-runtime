from typing import Protocol

from agent_runtime.domain.tool.tool_specification import ToolSpecification


class ToolCatalog(Protocol):
    def tools(self) -> list[ToolSpecification]: ...
