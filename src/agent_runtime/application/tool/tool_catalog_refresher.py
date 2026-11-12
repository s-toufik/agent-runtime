import asyncio
from collections.abc import Sequence

from pycraftcore.logger.port import Logger

from agent_runtime.application.port.outbound.tool_provider import ToolPort, ToolSource
from agent_runtime.application.tool.tool_registry import ToolRegistry
from agent_runtime.domain.tool.registry_change import RegistryChange


class ToolCatalogRefresher:
    def __init__(
        self,
        sources: Sequence[ToolSource],
        registry: ToolRegistry,
        logger: Logger,
    ) -> None:
        self._sources = tuple(sources)
        self._registry = registry
        self._logger = logger
        self._down: set[str] = set()
        self._seen: set[str] = set()
        self._wake_ups: dict[str, asyncio.Event] = {
            source.name: asyncio.Event() for source in self._sources
        }

    @property
    def unavailable(self) -> frozenset[str]:
        return frozenset(self._down)

    def wake(self) -> None:
        for wake_up in self._wake_ups.values():
            wake_up.set()

    async def refresh(self) -> bool:
        for source in self._sources:
            await self._refresh(source)
        return not self._down

    async def run(self) -> None:
        async with asyncio.TaskGroup() as group:
            for source in self._sources:
                group.create_task(self._keep_refreshing(source), name=f"refresh-{source.name}")

    async def _keep_refreshing(self, source: ToolSource) -> None:
        failures: int = 1 if source.name in self._down else 0
        while True:
            await self._pause(source.name, source.policy.delay_after(failures))
            failures = 0 if await self._refresh(source) else failures + 1

    async def _pause(self, name: str, seconds: float) -> None:
        wake_up: asyncio.Event = self._wake_ups[name]
        try:
            await asyncio.wait_for(wake_up.wait(), timeout=seconds)
        except TimeoutError:
            pass
        wake_up.clear()

    async def _refresh(self, source: ToolSource) -> bool:
        name: str = source.name
        try:
            tools: list[ToolPort] = await source.provider.tools()
            if not tools:
                raise LookupError("it advertises no tool yet")
        except Exception as exception:
            if name not in self._down:
                self._down.add(name)
                self._logger.warning(
                    f"MCP server '{name}' unavailable, its tools are missing until it is back "
                    f"(retrying in the background): {exception}"
                )
            return False

        if name in self._down:
            self._down.discard(name)
            self._logger.info(f"MCP server '{name}' is back")
        change: RegistryChange = self._registry.replace(name, tools)
        if change.conflicts:
            self._logger.warning(
                f"MCP server '{name}': tools skipped, their names are taken: "
                f"{', '.join(change.conflicts)}"
            )
        if name not in self._seen:
            self._seen.add(name)
            self._logger.info(
                f"Discovered {len(tools)} MCP tools from '{name}': "
                f"{', '.join(tool.specification.name for tool in tools)}"
            )
        elif change:
            self._logger.info(
                f"MCP server '{name}' tools changed"
                f"{_listed(' added', change.added)}{_listed(' removed', change.removed)}"
            )
        return True


def _listed(label: str, names: tuple[str, ...]) -> str:
    return f";{label}: {', '.join(names)}" if names else ""
