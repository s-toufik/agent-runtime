from dataclasses import replace

from pycraftcore.application_configuration.model import McpConnector

from agent_runtime.domain.agent.tool_scope import ToolScope


def scoped_connector(connector: McpConnector, scope: ToolScope) -> McpConnector:
    if scope.is_all:
        return connector
    return replace(connector, base_url=f"{connector.base_url.rstrip('/')}/{scope.name}")
