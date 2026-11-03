from functools import cached_property

from pycraftcore.application_configuration import ApplicationConfiguration
from pycraftcore.application_configuration.model.server import AsgiServer
from pycraftcore.logger.port import Logger
from pycraftcore.web.actuator import Actuator

from agent_runtime.adapter.inbound.web.stream.stream_agent_controller import (
    StreamAgentController,
)
from agent_runtime.adapter.outbound.event.queue_turn_event_stream import QueueTurnEventStream
from agent_runtime.application.port.inbound.list_models_port import ListModelsPort
from bootstrap.di.agent_di import AgentDI
from src import (
    APPLICATION_AUTHORS_EMAIL,
    APPLICATION_DEPLOYMENT_ENVIRONMENT,
    APPLICATION_NAME,
    APPLICATION_VERSION,
)


class AgentContainer(AgentDI):
    _ready: bool = False
    _stream_agent_controller: StreamAgentController | None = None

    @property
    def logging(self) -> Logger:
        return self._logging

    @property
    def application_configuration(self) -> ApplicationConfiguration:
        return self._configuration

    @property
    def server(self) -> AsgiServer:
        return self._server

    @property
    def stream_agent_controller(self) -> StreamAgentController:
        if self._stream_agent_controller is None:
            raise RuntimeError("The agent container is not booted")
        return self._stream_agent_controller

    @cached_property
    def list_models(self) -> ListModelsPort:
        return self._list_models()

    @cached_property
    def actuator(self) -> Actuator:
        return Actuator(
            name=APPLICATION_NAME,
            version=APPLICATION_VERSION,
            environment=APPLICATION_DEPLOYMENT_ENVIRONMENT,
            authors=APPLICATION_AUTHORS_EMAIL,
            is_ready=lambda: self.is_ready,
        )

    async def boot(self) -> None:
        _ = self._llm_transport_factory
        await self._start_factories()
        self._stream_agent_controller = StreamAgentController(
            await self._handle_message(),
            QueueTurnEventStream,
            self._logging,
            max_concurrent_streams=self._server_parameters.max_concurrent_streams,
        )
        self._ready = True
        self.logging.info("Agent container booted")

    async def stop(self) -> None:
        self._ready = False
        await self.close()
        self.logging.info("Agent container shut down")

    @property
    def is_ready(self) -> bool:
        return self._ready
