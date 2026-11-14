from collections.abc import Callable

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler, RequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types.a2a_pb2 import AgentCard
from fastapi import FastAPI
from pycraftcore.logger.port import Logger
from pycraftcore.web.actuator import Actuator
from pycraftcore.web.schema import ApiSettings

from agent_runtime.adapter.inbound.a2a.agent_card import agent_card
from agent_runtime.adapter.inbound.web.stream.stream_agent_controller import (
    StreamAgentController,
)
from agent_runtime.application.port.inbound.list_models_port import ListModelsPort
from agent_runtime.domain.a2a.agent_profile import AgentProfile
from bootstrap.application.fastapi.fastapi_api import create_fastapi_api
from tests.support.web import nothing

ACTUATOR = Actuator("agent-runtime", "1.0.0", "test", "team@example.com", lambda: True)
CARD: AgentCard = agent_card(AgentProfile("agent-runtime", "1.2.3"))


class IdleExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise RuntimeError("no A2A executor in this test")

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None: ...


def a2a_handler(executor: AgentExecutor, card: AgentCard = CARD) -> RequestHandler:
    return DefaultRequestHandler(
        agent_executor=executor, task_store=InMemoryTaskStore(), agent_card=card
    )


def fastapi_api(
    logger: Logger,
    agent: Callable[[], StreamAgentController],
    models: Callable[[], ListModelsPort],
    a2a: RequestHandler | None = None,
    card: AgentCard = CARD,
) -> FastAPI:
    return create_fastapi_api(
        ApiSettings(title="agent-runtime"),
        lifespan=nothing,
        agent=agent,
        models=models,
        a2a_handler=a2a or a2a_handler(IdleExecutor(), card),
        agent_card=card,
        actuator=ACTUATOR,
        logger=logger,
    )
