from functools import cached_property

from pycraftcore.application_configuration import ApplicationConfiguration
from pycraftcore.application_configuration.model.server import AsgiServer
from pycraftcore.logger.port import Logger
from pycraftcore.web.actuator import ActuatorRouter
from pycraftcore.web.schema import HttpRoute

from agent_runtime.adapter.inbound.web.controller.list_models_controller import (
    ListModelsController,
)
from agent_runtime.adapter.inbound.web.controller.stream_agent_controller import (
    StreamAgentController,
)
from agent_runtime.adapter.outbound.event.queue_turn_event_stream import QueueTurnEventStream
from bootstrap.di.agent_di import AgentDI
from bootstrap.router.agent.list_models_router import ListModelsRouter
from bootstrap.router.agent.stream_agent_router import StreamAgentRouter
from src import (
    APPLICATION_AUTHORS_EMAIL,
    APPLICATION_DEPLOYMENT_ENVIRONMENT,
    APPLICATION_NAME,
    APPLICATION_VERSION,
)


class AgentContainer(AgentDI):
    _ready: bool = False

    @property
    def logging(self) -> Logger:
        return self._logging

    @property
    def application_configuration(self) -> ApplicationConfiguration:
        return self._configuration

    @property
    def server(self) -> AsgiServer:
        return self._server

    @cached_property
    def _routes(self) -> list[HttpRoute]:
        return []

    async def boot(self) -> None:
        _ = self._llm_transport_factory
        await self._start_factories()
        await self._create_routes()
        self._ready = True
        self.logging.info("Agent container booted")

    async def stop(self) -> None:
        self._ready = False
        await self.close()
        self.logging.info("Agent container shut down")

    @property
    def routes(self) -> list[HttpRoute]:
        return self._routes

    async def _create_routes(self) -> None:
        self._routes.extend(await self._stream_agent_routes())
        self._routes.extend(self._list_models_routes())
        self._routes.extend(self._actuator_routes())

    async def _stream_agent_routes(self) -> list[HttpRoute]:
        controller = StreamAgentController(
            await self._handle_message(),
            QueueTurnEventStream,
            self._logging,
            max_concurrent_streams=self._server_parameters.max_concurrent_streams,
        )
        return StreamAgentRouter(controller).routes

    def _list_models_routes(self) -> list[HttpRoute]:
        controller = ListModelsController(self._list_models(), self._logging)
        return ListModelsRouter(controller).routes

    def _actuator_routes(self) -> list[HttpRoute]:
        return ActuatorRouter(
            app_name=APPLICATION_NAME,
            app_version=APPLICATION_VERSION,
            app_deployment_environment=APPLICATION_DEPLOYMENT_ENVIRONMENT,
            app_authors=APPLICATION_AUTHORS_EMAIL,
            is_ready=lambda: self.is_ready,
        ).routes

    @property
    def is_ready(self) -> bool:
        return self._ready
