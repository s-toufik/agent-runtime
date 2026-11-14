from functools import cached_property

from agent_runtime.application.use_case.handle_message import HandleMessage
from agent_runtime.application.use_case.list_models import ListModels
from bootstrap.configuration.server_parameters import ServerParameters
from bootstrap.di.base_di import BaseDI
from bootstrap.di.models_di import ModelsDI
from bootstrap.di.storage_di import StorageDI
from bootstrap.di.tools_di import ToolsDI
from bootstrap.di.workflow_di import WorkflowDI


class AgentDI(BaseDI):
    @cached_property
    def _server_parameters(self) -> ServerParameters:
        return ServerParameters.of(self._server)

    @cached_property
    def _tools(self) -> ToolsDI:
        return ToolsDI(self._configuration, self._logging)

    @cached_property
    def _models(self) -> ModelsDI:
        return ModelsDI(self._configuration, self._logging, self._telemetry_provider)

    @cached_property
    def _storage(self) -> StorageDI:
        return StorageDI(self._configuration, self._logging, self._register_repository)

    @cached_property
    def _workflow(self) -> WorkflowDI:
        return WorkflowDI(
            self._models.chat_models,
            self._logging,
            answer_delivery=self._server_parameters.answer_delivery,
            screen=self._settings.guardrail_enabled,
        )

    async def _handle_message(self) -> HandleMessage:
        runner = self._workflow.runner(
            await self._tools.toolbox(), await self._storage.checkpointer()
        )
        return HandleMessage(runner, self._models.catalog, self._logging)

    def _list_models(self) -> ListModels:
        return ListModels(self._models.catalog)

    async def close(self) -> None:
        await self._stop_factories()
        for module in (self.__dict__.get("_models"), self.__dict__.get("_tools")):
            if module is not None:
                await module.close()
        await self._shutdown_telemetry()
