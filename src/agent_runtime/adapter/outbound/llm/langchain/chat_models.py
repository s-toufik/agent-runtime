from collections.abc import Mapping

from httpx import AsyncClient
from langchain_core.language_models import BaseChatModel

from agent_runtime.adapter.outbound.llm.langchain.chat_factory import LLMChat
from agent_runtime.adapter.outbound.llm.model_catalog import AgentRole, ModelCatalog


class ChatModels:
    def __init__(
        self, catalog: ModelCatalog, http_clients: Mapping[str, AsyncClient] | None = None
    ) -> None:
        self._catalog = catalog
        self._http_clients = dict(http_clients or {})
        self._clients: dict[tuple[str, str, str], BaseChatModel] = {}

    def for_role(self, role: AgentRole, model: str) -> BaseChatModel:
        connector, parameters = self._catalog.settings_for(role, model)
        key = (connector.name, connector.base_url, parameters.model_dump_json())
        if key not in self._clients:
            self._clients[key] = LLMChat(
                connector, parameters, self._http_clients.get(connector.name)
            ).create_chat_client()
        return self._clients[key]
