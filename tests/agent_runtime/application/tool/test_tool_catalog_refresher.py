import asyncio

from agent_runtime.application.port.outbound.tool_provider import ToolSource
from agent_runtime.application.tool.tool_catalog_refresher import ToolCatalogRefresher
from agent_runtime.application.tool.tool_registry import ToolRegistry
from agent_runtime.domain.tool.refresh_policy import RefreshPolicy
from tests.agent_runtime.application.tool.test_tool_registry import StubTool


class Server:
    def __init__(self, *names: str, up: bool = True) -> None:
        self.names = list(names)
        self.up = up
        self.calls = 0

    async def tools(self):
        self.calls += 1
        if not self.up:
            raise ConnectionError("refused")
        return [StubTool(name) for name in self.names]


def names(registry: ToolRegistry) -> list[str]:
    return [spec.name for spec in registry.specifications()]


async def test_a_server_down_at_start_gives_its_tools_once_it_is_back(logger) -> None:
    toolbox = Server("echo", up=False)
    registry = ToolRegistry()
    refresher = ToolCatalogRefresher([ToolSource("toolbox", toolbox)], registry, logger)

    assert await refresher.refresh() is False
    assert refresher.unavailable == {"toolbox"}
    toolbox.up = True
    assert await refresher.refresh() is True

    assert names(registry) == ["echo"]
    assert "MCP server 'toolbox' is back" in logger.messages("info")


async def test_a_server_that_goes_down_keeps_its_tools_and_warns_once(logger) -> None:
    toolbox = Server("echo")
    registry = ToolRegistry()
    refresher = ToolCatalogRefresher([ToolSource("toolbox", toolbox)], registry, logger)
    await refresher.refresh()

    toolbox.up = False
    await refresher.refresh()
    await refresher.refresh()

    assert names(registry) == ["echo"]
    assert len([m for m in logger.messages("warning") if "'toolbox' unavailable" in m]) == 1


async def test_a_server_that_lists_no_tool_yet_is_retried_and_keeps_what_it_had(logger) -> None:
    toolbox = Server("echo")
    registry = ToolRegistry()
    refresher = ToolCatalogRefresher([ToolSource("toolbox", toolbox)], registry, logger)
    await refresher.refresh()

    toolbox.names = []

    assert await refresher.refresh() is False
    assert names(registry) == ["echo"]


async def test_new_and_removed_tools_are_picked_up(logger) -> None:
    toolbox = Server("echo", "old")
    registry = ToolRegistry()
    refresher = ToolCatalogRefresher([ToolSource("toolbox", toolbox)], registry, logger)
    await refresher.refresh()

    toolbox.names = ["echo", "new"]
    await refresher.refresh()

    assert names(registry) == ["echo", "new"]
    assert any("added: new" in m and "removed: old" in m for m in logger.messages("info"))


async def test_each_server_keeps_its_own_pace(logger) -> None:
    toolbox, grafana = Server("echo"), Server("grafana_search", up=False)
    refresher = ToolCatalogRefresher(
        [
            ToolSource("toolbox", toolbox, RefreshPolicy(interval=30, retry_delay=5)),
            ToolSource("grafana", grafana, RefreshPolicy(interval=30, retry_delay=0.01)),
        ],
        ToolRegistry(),
        logger,
    )
    await refresher.refresh()
    running = asyncio.create_task(refresher.run())

    async with asyncio.timeout(2):
        while grafana.calls < 4:
            await asyncio.sleep(0.01)

    running.cancel()
    assert toolbox.calls == 1


async def test_waking_it_refreshes_at_once_instead_of_waiting(logger) -> None:
    toolbox = Server("echo", up=False)
    registry = ToolRegistry()
    refresher = ToolCatalogRefresher(
        [ToolSource("toolbox", toolbox, RefreshPolicy(interval=30, retry_delay=30))],
        registry,
        logger,
    )
    await refresher.refresh()
    running = asyncio.create_task(refresher.run())

    toolbox.up = True
    refresher.wake()
    async with asyncio.timeout(2):
        while not names(registry):
            await asyncio.sleep(0.01)

    running.cancel()
    assert names(registry) == ["echo"]


async def test_without_servers_there_is_no_loop(logger) -> None:
    refresher = ToolCatalogRefresher([], ToolRegistry(), logger)

    await asyncio.wait_for(refresher.run(), timeout=1)
