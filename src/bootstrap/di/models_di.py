from collections.abc import Mapping
from functools import cached_property

from httpx import AsyncClient
from pycraftcore.application_configuration import ApplicationConfiguration
from pycraftcore.application_configuration.model import ApiConnector, ApiOperation
from pycraftcore.circuit_breaker.configuration import CircuitBreakerSettings
from pycraftcore.http.configuration import HttpClientSettings, LimitsSettings
from pycraftcore.http.policy.http_error_policy import is_business_error
from pycraftcore.logger.port import Logger
from pycraftcore.resilient_http.adapter import ResilientTransportFactory
from pycraftcore.resilient_http.configuration import ResilientHttpSettings
from pycraftcore.retry.configuration import RetrySettings
from pycraftcore.telemetry.port import TelemetryProvider

from agent_runtime.adapter.outbound.llm.langchain.chat_models import ChatModels
from agent_runtime.adapter.outbound.llm.mapper import ModelSettingsMapper
from agent_runtime.adapter.outbound.llm.model_catalog import (
    AgentRole,
    ModelCatalog,
    ModelSettings,
)
from agent_runtime.adapter.outbound.llm.retry_policy import should_retry_model_call


class ModelsDI:
    def __init__(
        self,
        configuration: ApplicationConfiguration,
        logger: Logger,
        telemetry: TelemetryProvider,
    ) -> None:
        self._configuration = configuration
        self._logger = logger
        self._telemetry = telemetry

    @cached_property
    def catalog(self) -> ModelCatalog:
        roles: set[str] = {role.value for role in AgentRole}
        models: dict[str, ModelSettings] = {}
        for name, operation in self._configuration.operation.by_name.items():
            if name in roles or not isinstance(operation, ApiOperation):
                continue
            if operation.connector.name not in self.connectors:
                continue
            connector, parameters = ModelSettingsMapper(operation)()
            if parameters.model_name in models:
                self._logger.warning(
                    f"Model '{parameters.model_name}' is declared twice; keeping the one of "
                    f"'{models[parameters.model_name][0].name}'"
                )
                continue
            models[parameters.model_name] = (connector, parameters)
        if not models:
            self._logger.warning("No model provider has a URL: the agent has no model to use")
        return ModelCatalog(models=models, roles=self.frozen_roles(models))

    @cached_property
    def chat_models(self) -> ChatModels:
        return ChatModels(self.catalog, self.http_clients)

    @cached_property
    def connectors(self) -> dict[str, ApiConnector]:
        declared: dict[str, ApiConnector] = {
            operation.connector.name: operation.connector
            for operation in self._configuration.operation.by_name.values()
            if isinstance(operation, ApiOperation)
        }
        for name, connector in declared.items():
            if not connector.base_url.strip():
                self._logger.info(f"Model provider '{name}' has no URL: its models are left out")
        return {name: c for name, c in declared.items() if c.base_url.strip()}

    @cached_property
    def http_clients(self) -> dict[str, AsyncClient]:
        return {
            name: self.transport_factory(connector).create_async_client()
            for name, connector in self.connectors.items()
        }

    def transport_factory(self, connector: ApiConnector) -> ResilientTransportFactory:
        http_settings = HttpClientSettings(limits=LimitsSettings(timeout=connector.timeout))
        http_settings.client_params.base_url = connector.base_url
        http_settings.security.certificate = connector.certificate

        settings = ResilientHttpSettings(
            http=http_settings,
            retry=RetrySettings(
                retry_count=connector.retry,
                retry_delay=1,
                max_retry_delay=20,
                jitter=1,
                should_retry=should_retry_model_call,
            ),
            circuit_breaker=CircuitBreakerSettings(
                failure_threshold=3,
                recovery_timeout=30,
                is_excluded=is_business_error,
                name=f"llm-{connector.name}",
            ),
        )

        return ResilientTransportFactory(
            settings=settings,
            trace_manager=self._telemetry.tracer(f"llm-{connector.name}"),
            logger=self._logger,
        )

    def frozen_roles(self, models: Mapping[str, ModelSettings]) -> dict[AgentRole, ModelSettings]:
        frozen: dict[AgentRole, ModelSettings] = {}
        for role in AgentRole:
            operation = self._configuration.operation.by_name.get(role.value)
            if not isinstance(operation, ApiOperation) or not operation.parameters.get("model"):
                continue
            connector, parameters = ModelSettingsMapper(operation)()
            served = models.get(parameters.model_name)
            frozen[role] = (served[0] if served else connector, parameters)
        return frozen

    async def close(self) -> None:
        clients: dict[str, AsyncClient] = self.__dict__.pop("http_clients", {})
        for client in clients.values():
            await client.aclose()
