from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from litestar import Litestar
from litestar.di import Provide
from litestar.routes import HTTPRoute
from pycraftcore.logger.port import Logger
from pycraftcore.web.actuator import Actuator
from pycraftcore.web.schema import ApiSettings
from pycraftcore.web_litestar import actuator_router, create_app, detail_handler

from agent_runtime.adapter.inbound.web.exception.server_at_capacity_exception import (
    ServerAtCapacityException,
)
from agent_runtime.adapter.inbound.web.stream.stream_agent_controller import (
    StreamAgentController,
)
from agent_runtime.application.port.inbound.list_models_port import ListModelsPort
from bootstrap.application.litestar.router.agent_router import AgentRouter


def create_litestar_api(
    api: ApiSettings,
    *,
    lifespan: Callable[[], AbstractAsyncContextManager[None]],
    agent: Callable[[], StreamAgentController],
    models: Callable[[], ListModelsPort],
    actuator: Actuator,
    logger: Logger,
) -> Litestar:
    return create_app(
        api,
        routes=[AgentRouter, actuator_router(actuator)],
        lifespan=lifespan,
        exception_handlers={ServerAtCapacityException: detail_handler(503)},
        dependencies={
            "agent": Provide(agent, sync_to_thread=False),
            "models": Provide(models, sync_to_thread=False),
        },
        on_startup=[_log_routes(logger)],
    )


def _log_routes(logger: Logger) -> Callable[[Litestar], None]:
    def log(app: Litestar) -> None:
        for route in app.routes:
            if isinstance(route, HTTPRoute):
                methods = " ".join(sorted(route.methods - {"OPTIONS", "HEAD"}))
                logger.info(f"Route {methods} {route.path} included")

    return log
