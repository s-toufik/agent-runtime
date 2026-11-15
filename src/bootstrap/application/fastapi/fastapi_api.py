from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from a2a.server.request_handlers import RequestHandler
from a2a.types.a2a_pb2 import AgentCard
from fastapi import FastAPI
from fastapi.routing import APIRoute, iter_route_contexts
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pycraftcore.logger.port import Logger
from pycraftcore.web.actuator import ACTUATOR_PATH, Actuator
from pycraftcore.web.schema import ApiSettings
from pycraftcore.web_fastapi import actuator_router, create_app, detail_handler

from agent_runtime.adapter.inbound.exception.server_at_capacity_exception import (
    ServerAtCapacityException,
)
from agent_runtime.adapter.inbound.web.stream.stream_agent_controller import (
    StreamAgentController,
)
from agent_runtime.application.port.inbound.describe_a2a_options_port import (
    DescribeA2aOptionsPort,
)
from agent_runtime.application.port.inbound.list_agents_port import ListAgentsPort
from agent_runtime.application.port.inbound.list_models_port import ListModelsPort
from agent_runtime.domain.agent.agent_routes import AgentRoutes
from bootstrap.application.fastapi.router.a2a_router import a2a_card_router, mount_a2a
from bootstrap.application.fastapi.router.agent_router import agent_router


def create_fastapi_api(
    api: ApiSettings,
    *,
    lifespan: Callable[[], AbstractAsyncContextManager[None]],
    agent: Callable[[], StreamAgentController],
    models: Callable[[], ListModelsPort],
    agents: Callable[[], ListAgentsPort],
    a2a_handler: RequestHandler,
    agent_card: AgentCard,
    a2a_options: Callable[[], DescribeA2aOptionsPort],
    routes: AgentRoutes,
    actuator: Actuator,
    logger: Logger,
) -> FastAPI:
    app: FastAPI = create_app(
        api,
        routes=[
            agent_router(agent, models, agents, routes),
            a2a_card_router(agent_card, a2a_options, routes.a2a),
            actuator_router(actuator),
        ],
        lifespan=lambda: _logging_routes(lifespan, app, logger),
        exception_handlers={ServerAtCapacityException: detail_handler(503)},
    )
    mount_a2a(app, a2a_handler, api.base_path, routes.a2a)
    FastAPIInstrumentor.instrument_app(
        app, excluded_urls=ACTUATOR_PATH, exclude_spans=["receive", "send"]
    )
    return app


@asynccontextmanager
async def _logging_routes(
    lifespan: Callable[[], AbstractAsyncContextManager[None]], app: FastAPI, logger: Logger
) -> AsyncGenerator[None]:
    async with lifespan():
        for route in iter_route_contexts(app.routes):
            if isinstance(route.route, APIRoute):
                methods = " ".join(sorted(set(route.methods or ()) - {"OPTIONS", "HEAD"}))
                logger.info(f"Route {methods} {route.path} included")
        yield
