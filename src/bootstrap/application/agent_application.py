import traceback
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from pycraftcore.http.middleware import RequestIDMiddleware
from pycraftcore.web.asgi import ASGIApp
from pycraftcore.web.frameworks import web_application_factory
from pycraftcore.web.schema import WebApplication

from agent_runtime.adapter.inbound.web.exception.server_at_capacity_exception import (
    ServerAtCapacityException,
)
from bootstrap.configuration.settings import ProcessSettings
from bootstrap.container.agent_container import AgentContainer


@asynccontextmanager
async def _lifespan(container: AgentContainer) -> AsyncGenerator[None]:
    try:
        await container.boot()
    except Exception as exception:
        container.logging.critical(
            "Agent container failed to boot:\n" + "".join(traceback.format_exception(exception))
        )
        raise

    for route in container.routes:
        container.logging.info(
            f"Route {route.method} {container.server.base_path}{route.path} included"
        )

    try:
        yield
    finally:
        await container.stop()


def create_agent_application(settings: ProcessSettings | None = None) -> ASGIApp:
    process_settings = settings or ProcessSettings.for_role("agent-runtime")
    container = AgentContainer(process_settings)
    server = container.server

    application = WebApplication(
        title=server.name,
        lifespan=lambda: _lifespan(container),
        routes=lambda: container.routes,
        base_path=server.base_path,
        errors={ServerAtCapacityException: 503},
        middleware=(RequestIDMiddleware,),
        cors_origins=server.cors_origins,
    )
    return web_application_factory(server.framework).create(application)
