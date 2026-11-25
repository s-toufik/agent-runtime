import os
from collections.abc import Mapping
from functools import cached_property

from pycraftcore.application_configuration import ApplicationConfiguration
from pycraftcore.application_configuration.enum import ConnectorType
from pycraftcore.application_configuration.model import A2aConnector, McpConnector, McpOperation
from pycraftcore.logger.port import Logger
from pycraftcore.mcp_sdk import SdkMcpClient

from agent_runtime.adapter.outbound.agent.a2a.a2a_peer_agents import A2aPeerAgents
from agent_runtime.adapter.outbound.langgraph.langgraph_event_publisher import (
    LangGraphEventPublisher,
)
from agent_runtime.adapter.outbound.telemetry.otel_delegation_meter import OtelDelegationMeter
from agent_runtime.adapter.outbound.tool.mcp.mcp_tool_provider import McpToolProvider
from agent_runtime.adapter.outbound.tool.mcp.scoped_endpoint import scoped_connector
from agent_runtime.adapter.outbound.tool.toolbox import Toolbox
from agent_runtime.application.agent.delegate_tasks_tool import DelegateTasksProvider
from agent_runtime.application.agent.peer_directory import PeerDirectory
from agent_runtime.application.port.outbound.tool_provider import ToolSource
from agent_runtime.application.tool.tool_catalog_refresher import ToolCatalogRefresher
from agent_runtime.application.tool.tool_registry import ToolRegistry
from agent_runtime.domain.agent.tool_scope import ToolScope
from bootstrap.configuration.peer_connectors import PEER_TEMPLATE, peer_connectors

MCP_CONNECTOR_NAME: str = "toolbox"
EXTERNAL_MCP_PREFIX: str = "external_mcp_"
PEER_SOURCE: str = "agents"


class ToolsDI:
    def __init__(
        self,
        configuration: ApplicationConfiguration,
        logger: Logger,
        scope: ToolScope | None = None,
        peers: tuple[str, ...] = (),
    ) -> None:
        self._configuration = configuration
        self._logger = logger
        self._scope = scope or ToolScope()
        self._peers = peers

    @cached_property
    def registry(self) -> ToolRegistry:
        return ToolRegistry()

    @cached_property
    def refresher(self) -> ToolCatalogRefresher:
        connectors: dict[str, McpConnector] = self.connectors
        return ToolCatalogRefresher(
            [
                ToolSource(name, McpToolProvider(client, required=False), connectors[name].refresh)
                for name, client in self.clients.items()
            ]
            + self._peer_sources(),
            self.registry,
            self._logger,
        )

    @cached_property
    def connectors(self) -> dict[str, McpConnector]:
        declared: Mapping[str, McpConnector] = self._configuration.connector[ConnectorType.mcp]
        external: dict[str, McpConnector] = {
            name: declared[name]
            for name in sorted(declared)
            if name.startswith(EXTERNAL_MCP_PREFIX)
        }
        if not self._scope.uses_toolbox:
            return external
        toolbox: McpConnector = scoped_connector(declared[MCP_CONNECTOR_NAME], self._scope)
        return {MCP_CONNECTOR_NAME: toolbox, **external}

    @cached_property
    def clients(self) -> dict[str, SdkMcpClient]:
        operations: dict[str, McpOperation] = self._operations
        return {
            name: SdkMcpClient(connector, operations.get(connector.name), self._logger)
            for name, connector in self.connectors.items()
        }

    @cached_property
    def peer_directory(self) -> PeerDirectory:
        return PeerDirectory()

    @cached_property
    def peer_agents(self) -> A2aPeerAgents:
        template: A2aConnector = self._configuration.connector.a2a(PEER_TEMPLATE)
        return A2aPeerAgents(peer_connectors(template, self._peers, os.environ), self._logger)

    def _peer_sources(self) -> list[ToolSource]:
        if not self._peers:
            return []
        missing: list[str] = [name for name in self._peers if name not in self.peer_agents.names]
        if missing:
            self._logger.info(f"Agents without a URL, not called: {', '.join(missing)}")
        if not self.peer_agents.names:
            return []
        provider = DelegateTasksProvider(
            self.peer_agents, self.peer_directory, LangGraphEventPublisher(), OtelDelegationMeter()
        )
        return [ToolSource(PEER_SOURCE, provider)]

    async def toolbox(self) -> Toolbox:
        await self.refresher.refresh()
        if not self._scope.uses_toolbox:
            self._logger.info("The agent's tool scope is 'none': it takes no toolbox tools")
        elif not len(self.registry):
            self._logger.warning(
                "No MCP tools available yet: the agent answers without tools until its MCP "
                "servers are back"
            )
        return Toolbox(self.registry, self._logger, on_unknown_tool=self.refresher.wake)

    async def close(self) -> None:
        peers: A2aPeerAgents | None = self.__dict__.pop("peer_agents", None)
        if peers is not None:
            await peers.close()

    @cached_property
    def _operations(self) -> dict[str, McpOperation]:
        return {
            operation.connector.name: operation
            for operation in self._configuration.operation.by_name.values()
            if isinstance(operation, McpOperation)
        }
