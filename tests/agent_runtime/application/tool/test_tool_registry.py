import pytest

from agent_runtime.application.tool.tool_registry import ToolRegistry
from agent_runtime.domain.exception.unknown_tool_exception import UnknownToolException
from agent_runtime.domain.tool.tool_call import ToolCall
from agent_runtime.domain.tool.tool_result import ToolResult
from agent_runtime.domain.tool.tool_specification import ToolSpecification


class StubTool:
    def __init__(self, name: str) -> None:
        self._specification = ToolSpecification(
            name=name, description=f"{name} tool.", parameters={"type": "object"}
        )

    @property
    def specification(self) -> ToolSpecification:
        return self._specification

    async def invoke(self, call: ToolCall) -> ToolResult:  # pragma: no cover
        return ToolResult(call_id=call.id, tool_name=call.name, output="")


def test_lookup_by_name() -> None:
    registry = ToolRegistry([StubTool("a"), StubTool("b")])

    assert registry.get("a").specification.name == "a"
    assert len(registry) == 2


def test_unknown_tool_raises_a_domain_exception() -> None:
    registry = ToolRegistry([StubTool("a")])

    with pytest.raises(UnknownToolException):
        registry.get("missing")


def test_a_source_s_tools_are_replaced_by_its_next_list() -> None:
    registry = ToolRegistry()

    first = registry.replace("toolbox", [StubTool("a"), StubTool("b")])
    second = registry.replace("toolbox", [StubTool("a"), StubTool("c")])

    assert first.added == ("a", "b")
    assert (second.added, second.removed) == (("c",), ("b",))
    assert [spec.name for spec in registry.specifications()] == ["a", "c"]
    assert not registry.replace("toolbox", [StubTool("a"), StubTool("c")])


def test_a_name_another_source_owns_is_skipped_as_a_conflict() -> None:
    registry = ToolRegistry()
    registry.replace("toolbox", [StubTool("a")])

    change = registry.replace("external_mcp_analytics", [StubTool("a"), StubTool("z")])

    assert change.conflicts == ("a",)
    assert change.added == ("z",)
