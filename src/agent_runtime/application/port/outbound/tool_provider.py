from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from agent_runtime.domain.tool.refresh_policy import RefreshPolicy
from agent_runtime.domain.tool.tool_call import ToolCall
from agent_runtime.domain.tool.tool_result import ToolResult
from agent_runtime.domain.tool.tool_specification import ToolSpecification


@runtime_checkable
class ToolPort(Protocol):
    @property
    def specification(self) -> ToolSpecification: ...

    async def invoke(self, call: ToolCall) -> ToolResult: ...


@runtime_checkable
class ToolProviderPort(Protocol):
    async def tools(self) -> list[ToolPort]: ...


@dataclass(frozen=True)
class ToolSource:
    name: str
    provider: ToolProviderPort
    policy: RefreshPolicy = field(default_factory=RefreshPolicy)
