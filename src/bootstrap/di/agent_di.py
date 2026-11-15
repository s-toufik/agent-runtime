from functools import cached_property

from agent_runtime.adapter.outbound.llm.langchain.prompts.generic_prompts import prompt_book
from agent_runtime.adapter.outbound.llm.langchain.prompts.prompt_book import PromptBook
from agent_runtime.application.agent.agent_models import AgentModels
from agent_runtime.application.use_case.handle_message import HandleMessage
from agent_runtime.application.use_case.list_models import ListModels
from agent_runtime.domain.agent.agent import Agent
from bootstrap.configuration.agent_definition import LoadAgentDefinition
from bootstrap.configuration.server_parameters import ServerParameters
from bootstrap.di.base_di import BaseDI
from bootstrap.di.models_di import ModelsDI
from bootstrap.di.storage_di import StorageDI
from bootstrap.di.tools_di import ToolsDI
from bootstrap.di.workflow_di import WorkflowDI


class AgentDI(BaseDI):
    @cached_property
    def _agent(self) -> Agent:
        return LoadAgentDefinition(self._settings.agents_directory, self._settings.agent)()

    @cached_property
    def _prompts(self) -> PromptBook:
        return prompt_book(self._agent.description, self._agent.prompts)

    @cached_property
    def _server_parameters(self) -> ServerParameters:
        return ServerParameters.of(self._server)

    @cached_property
    def _tools(self) -> ToolsDI:
        return ToolsDI(
            self._configuration, self._logging, self._agent.tool_scope, self._agent.peers
        )

    @cached_property
    def _agent_models(self) -> AgentModels:
        return AgentModels(self._models.catalog, self._agent.model)

    @cached_property
    def _models(self) -> ModelsDI:
        return ModelsDI(self._configuration, self._logging, self._telemetry_provider)

    @cached_property
    def _storage(self) -> StorageDI:
        return StorageDI(
            self._configuration, self._logging, self._register_repository, self._agent.name
        )

    @cached_property
    def _workflow(self) -> WorkflowDI:
        return WorkflowDI(
            self._models.chat_models,
            self._logging,
            answer_delivery=self._server_parameters.answer_delivery,
            prompts=self._prompts,
            shape=self._agent.turns,
        )

    async def _handle_message(self) -> HandleMessage:
        runner = self._workflow.runner(
            await self._tools.toolbox(), await self._storage.checkpointer()
        )
        return HandleMessage(runner, self._agent_models, self._logging)

    def _list_models(self) -> ListModels:
        return ListModels(self._agent_models)

    async def close(self) -> None:
        await self._stop_factories()
        for module in (self.__dict__.get("_models"), self.__dict__.get("_tools")):
            if module is not None:
                await module.close()
        await self._shutdown_telemetry()
