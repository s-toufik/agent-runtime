from collections.abc import Mapping
from functools import cached_property

from pycraftcore.application_configuration import ApplicationConfiguration
from pycraftcore.application_configuration.enum import ConnectorType
from pycraftcore.application_configuration.model.connector import McpConnector
from pycraftcore.application_configuration.model.operation import McpOperation
from pycraftcore.logger.port import Logger

from agent_runtime.adapter.outbound.tool.mcp.mcp_tool_provider import McpToolProvider
from agent_runtime.adapter.outbound.tool.mcp.streamable_http_session_factory import (
    StreamableHttpSessionFactory,
)
from agent_runtime.adapter.outbound.tool.toolbox import Toolbox
from agent_runtime.application.port.outbound.tool_provider import ToolSource
from agent_runtime.application.tool.tool_catalog_refresher import ToolCatalogRefresher
from agent_runtime.application.tool.tool_registry import ToolRegistry
from agent_runtime.domain.tool.refresh_policy import RefreshPolicy

MCP_CONNECTOR_NAME: str = "toolbox"
EXTERNAL_MCP_PREFIX: str = "external_mcp_"


class ToolsDI:
    def __init__(self, configuration: ApplicationConfiguration, logger: Logger) -> None:
        self._configuration = configuration
        self._logger = logger

    @cached_property
    def registry(self) -> ToolRegistry:
        return ToolRegistry()

    @cached_property
    def refresher(self) -> ToolCatalogRefresher:
        connectors: dict[str, McpConnector] = self.connectors
        return ToolCatalogRefresher(
            [
                ToolSource(
                    name,
                    McpToolProvider(factory, required=False),
                    refresh_policy(connectors.get(name)),
                )
                for name, factory in self.session_factories.items()
            ],
            self.registry,
            self._logger,
        )

    @cached_property
    def connectors(self) -> dict[str, McpConnector]:
        declared: Mapping[str, McpConnector] = self._configuration.connector[ConnectorType.mcp]
        names: list[str] = [MCP_CONNECTOR_NAME] + sorted(
            name for name in declared if name.startswith(EXTERNAL_MCP_PREFIX)
        )
        return {name: declared[name] for name in names}

    @cached_property
    def session_factories(self) -> dict[str, StreamableHttpSessionFactory]:
        operations: dict[str, McpOperation] = self._operations
        return {
            name: StreamableHttpSessionFactory(
                connector=connector,
                logger=self._logger,
                operation=operations.get(connector.name),
            )
            for name, connector in self.connectors.items()
        }

    async def toolbox(self) -> Toolbox:
        await self.refresher.refresh()
        if not len(self.registry):
            self._logger.warning(
                "No MCP tools available yet: the agent answers without tools until its MCP "
                "servers are back"
            )
        return Toolbox(self.registry, self._logger, on_unknown_tool=self.refresher.wake)

    async def close(self) -> None:
        self.__dict__.pop("session_factories", None)

    @cached_property
    def _operations(self) -> dict[str, McpOperation]:
        return {
            operation.connector.name: operation
            for operation in self._configuration.operation.by_name.values()
            if isinstance(operation, McpOperation)
        }


def refresh_policy(connector: McpConnector | None) -> RefreshPolicy:
    if connector is None:
        return RefreshPolicy()
    return RefreshPolicy(
        interval=connector.refresh.interval,
        retry_delay=connector.refresh.retry_delay,
        max_retry_delay=connector.refresh.max_retry_delay,
    )
