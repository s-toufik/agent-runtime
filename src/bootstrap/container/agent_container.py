import asyncio
from collections.abc import Coroutine
from contextlib import suppress
from functools import cached_property
from typing import Any

from a2a.server.request_handlers import RequestHandler
from a2a.server.tasks import TaskStore
from a2a.types.a2a_pb2 import AgentCard
from pycraftcore.application_configuration import ApplicationConfiguration
from pycraftcore.application_configuration.model.server import AsgiServer
from pycraftcore.logger.port import Logger
from pycraftcore.web.actuator import Actuator

from agent_runtime.adapter.inbound.web.stream.stream_agent_controller import (
    StreamAgentController,
)
from agent_runtime.adapter.outbound.event.queue_turn_event_stream import QueueTurnEventStream
from agent_runtime.application.port.inbound.list_models_port import ListModelsPort
from agent_runtime.application.port.inbound.run_a2a_task_port import RunA2aTaskPort
from agent_runtime.application.use_case.run_a2a_task import RunA2aTask
from agent_runtime.domain.a2a.agent_profile import AgentProfile
from bootstrap.di.a2a_di import A2aDI
from bootstrap.di.agent_di import AgentDI
from src import (
    APPLICATION_AUTHORS_EMAIL,
    APPLICATION_DEPLOYMENT_ENVIRONMENT,
    APPLICATION_NAME,
    APPLICATION_VERSION,
)

NOT_BOOTED: str = "The agent container is not booted"


class AgentContainer(AgentDI):
    _ready: bool = False
    _stream_agent_controller: StreamAgentController | None = None
    _run_a2a_task: RunA2aTaskPort | None = None
    _a2a_task_store: TaskStore | None = None

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
        return _booted(self._stream_agent_controller)

    @property
    def run_a2a_task(self) -> RunA2aTaskPort:
        return _booted(self._run_a2a_task)

    @property
    def a2a_task_store(self) -> TaskStore:
        return _booted(self._a2a_task_store)

    @property
    def a2a_agent_card(self) -> AgentCard:
        return self._a2a.card

    @property
    def a2a_request_handler(self) -> RequestHandler:
        return self._a2a.request_handler

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

    @cached_property
    def _a2a(self) -> A2aDI:
        return A2aDI(
            AgentProfile(APPLICATION_NAME, APPLICATION_VERSION),
            self._server_parameters,
            self._logging,
            run_task=lambda: self.run_a2a_task,
            task_store=lambda: self.a2a_task_store,
        )

    @cached_property
    def _background(self) -> list[asyncio.Task[None]]:
        return []

    async def boot(self) -> None:
        _ = self._models.http_clients
        await self._start_factories()
        handle_message = await self._handle_message()
        parameters = self._server_parameters
        self._stream_agent_controller = StreamAgentController(
            handle_message,
            QueueTurnEventStream,
            self._logging,
            max_concurrent_streams=parameters.max_concurrent_streams,
        )
        self._run_a2a_task = RunA2aTask(
            handle_message, QueueTurnEventStream, self.list_models, parameters.a2a_model
        )
        tasks_engine = await self._storage.a2a_tasks_engine()
        self._a2a_task_store = await self._a2a.task_store(tasks_engine)
        if not self._background:
            self._start("mcp-tool-refresher", self._tools.refresher.run())
            self._start("a2a-task-retention", self._a2a.retention(tasks_engine).run())
        self._ready = True
        self.logging.info("Agent container booted")

    async def stop(self) -> None:
        self._ready = False
        while self._background:
            task = self._background.pop()
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        await self.close()
        self.logging.info("Agent container shut down")

    @property
    def is_ready(self) -> bool:
        return self._ready

    def _start(self, name: str, work: Coroutine[Any, Any, None]) -> None:
        self._background.append(asyncio.create_task(work, name=name))


def _booted[T](value: T | None) -> T:
    if value is None:
        raise RuntimeError(NOT_BOOTED)
    return value
