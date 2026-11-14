from collections.abc import Callable
from datetime import timedelta
from functools import cached_property

from a2a.server.request_handlers import DefaultRequestHandler, RequestHandler
from a2a.server.tasks import TaskStore
from a2a.server.tasks.database_task_store import DatabaseTaskStore
from a2a.types.a2a_pb2 import AgentCard
from pycraftcore.logger.port import Logger
from sqlalchemy.ext.asyncio import AsyncEngine

from agent_runtime.adapter.inbound.a2a.a2a_agent_executor import A2aAgentExecutor
from agent_runtime.adapter.inbound.a2a.agent_card import agent_card
from agent_runtime.adapter.inbound.a2a.delegating_task_store import DelegatingTaskStore
from agent_runtime.adapter.inbound.a2a.task_retention import TaskRetention
from agent_runtime.application.port.inbound.run_a2a_task_port import RunA2aTaskPort
from agent_runtime.domain.a2a.agent_profile import AgentProfile
from bootstrap.configuration.server_parameters import ServerParameters


class A2aDI:
    def __init__(
        self,
        profile: AgentProfile,
        parameters: ServerParameters,
        logger: Logger,
        *,
        run_task: Callable[[], RunA2aTaskPort],
        task_store: Callable[[], TaskStore],
    ) -> None:
        self._profile = profile
        self._parameters = parameters
        self._logger = logger
        self._run_task = run_task
        self._task_store = task_store

    @cached_property
    def card(self) -> AgentCard:
        return agent_card(self._profile, self._parameters.a2a_url)

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

    async def task_store(self, engine: AsyncEngine) -> TaskStore:
        store = DatabaseTaskStore(engine)
        await store.initialize()
        return store

    def retention(self, engine: AsyncEngine) -> TaskRetention:
        return TaskRetention(engine, timedelta(seconds=self._parameters.a2a_task_ttl), self._logger)
