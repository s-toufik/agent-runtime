from collections.abc import Callable
from datetime import timedelta
from functools import cached_property

from a2a.server.request_handlers import DefaultRequestHandler, RequestHandler
from a2a.server.tasks import TaskStore
from a2a.server.tasks.database_task_store import DatabaseTaskStore
from a2a.types.a2a_pb2 import AgentCard
from pycraftcore.logger.port import Logger

from agent_runtime.adapter.inbound.a2a.a2a_agent_executor import A2aAgentExecutor
from agent_runtime.adapter.inbound.a2a.agent_card import agent_card
from agent_runtime.adapter.inbound.a2a.delegating_task_store import DelegatingTaskStore
from agent_runtime.adapter.inbound.a2a.task_retention import TaskRetention
from agent_runtime.application.port.inbound.run_a2a_task_port import RunA2aTaskPort
from agent_runtime.domain.agent.agent import Agent
from bootstrap.configuration.a2a_settings import A2aSettings
from bootstrap.configuration.server_parameters import ServerParameters
from bootstrap.di.storage_di import A2aTaskStorage

TASKS: str = "tasks"


class A2aDI:
    def __init__(
        self,
        agent: Agent,
        version: str,
        parameters: ServerParameters,
        settings: A2aSettings,
        logger: Logger,
        *,
        run_task: Callable[[], RunA2aTaskPort],
        task_store: Callable[[], TaskStore],
    ) -> None:
        self._agent = agent
        self._version = version
        self._parameters = parameters
        self._settings = settings
        self._logger = logger
        self._run_task = run_task
        self._task_store = task_store

    @cached_property
    def card(self) -> AgentCard:
        return agent_card(self._agent, self._version, self._settings.url)

    @cached_property
    def request_handler(self) -> RequestHandler:
        executor = A2aAgentExecutor(
            self._run_task,
            self._logger,
            max_concurrent_turns=self._parameters.max_concurrent_streams,
        )
        return DefaultRequestHandler(
            agent_executor=executor,
            task_store=DelegatingTaskStore(self._task_store),
            agent_card=self.card,
        )

    async def task_store(self, storage: A2aTaskStorage) -> DatabaseTaskStore:
        store = DatabaseTaskStore(storage.engine, table_name=storage.operation.collection(TASKS))
        await store.initialize()
        return store

    def retention(self, store: DatabaseTaskStore, storage: A2aTaskStorage) -> TaskRetention | None:
        ttl: int | None = storage.operation.ttl
        if ttl is None:
            self._logger.info(f"A2A tasks of '{storage.operation.name}' have no ttl: kept")
            return None
        return TaskRetention(storage.engine, store.task_model, timedelta(seconds=ttl), self._logger)
