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
from agent_runtime.application.agent.peer_directory import PeerDirectory
from agent_runtime.application.port.inbound.list_agents_port import ListAgentsPort
from agent_runtime.application.port.inbound.list_models_port import ListModelsPort
from agent_runtime.application.use_case.describe_a2a_options import DescribeA2aOptions
from agent_runtime.application.use_case.list_agents import ListAgents
from agent_runtime.domain.agent.agent_routes import AgentRoutes
from bootstrap.application.fastapi.fastapi_api import create_fastapi_api
from tests.support.agents import AGENT
from tests.support.web import nothing

ACTUATOR = Actuator("agent-runtime", "1.0.0", "test", "team@example.com", lambda: True)
CARD: AgentCard = agent_card(AGENT, "1.2.3")


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
    routes: AgentRoutes | None = None,
    agents: Callable[[], ListAgentsPort] | None = None,
) -> FastAPI:
    return create_fastapi_api(
        ApiSettings(title="agent-runtime"),
        lifespan=nothing,
        agent=agent,
        models=models,
        agents=agents or (lambda: ListAgents(AGENT, PeerDirectory())),
        a2a_handler=a2a or a2a_handler(IdleExecutor(), card),
        agent_card=card,
        a2a_options=lambda: DescribeA2aOptions(models()),
        routes=routes or AgentRoutes(),
        actuator=ACTUATOR,
        logger=logger,
    )
