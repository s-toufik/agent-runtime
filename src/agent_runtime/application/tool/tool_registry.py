from collections.abc import Iterable
from dataclasses import dataclass

from agent_runtime.application.port.outbound.tool_provider import ToolPort
from agent_runtime.domain.exception.unknown_tool_exception import UnknownToolException
from agent_runtime.domain.tool.registry_change import RegistryChange
from agent_runtime.domain.tool.tool_specification import ToolSpecification


@dataclass(frozen=True)
class _Entry:
    source: str | None
    tool: ToolPort


class ToolRegistry:
    def __init__(self, tools: Iterable[ToolPort] = ()) -> None:
        self._entries: dict[str, _Entry] = {
            tool.specification.name: _Entry(None, tool) for tool in tools
        }

    def get(self, name: str) -> ToolPort:
        entry: _Entry | None = self._entries.get(name)
        if entry is None:
            raise UnknownToolException(f"Unknown tool: '{name}'.")
        return entry.tool

    def specifications(self) -> list[ToolSpecification]:
        return [entry.tool.specification for entry in self._entries.values()]

    def replace(self, source: str, tools: Iterable[ToolPort]) -> RegistryChange:
        current: dict[str, ToolPort] = {
            name: entry.tool for name, entry in self._entries.items() if entry.source == source
        }
        wanted: dict[str, ToolPort] = {}
        conflicts: list[str] = []
        for tool in tools:
            name: str = tool.specification.name
            owner: _Entry | None = self._entries.get(name)
            if (owner is not None and owner.source != source) or name in wanted:
                conflicts.append(name)
                continue
            wanted[name] = tool

        removed: list[str] = [name for name in current if name not in wanted]
        added: list[str] = [
            name
            for name, tool in wanted.items()
            if name not in current or current[name].specification != tool.specification
        ]

        for name in removed:
            del self._entries[name]
        for name, tool in wanted.items():
            self._entries[name] = _Entry(source, tool)

        return RegistryChange(tuple(added), tuple(removed), tuple(conflicts))

    def __len__(self) -> int:
        return len(self._entries)
