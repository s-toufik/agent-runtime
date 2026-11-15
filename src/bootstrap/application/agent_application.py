import traceback
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from pycraftcore.web.asgi import ASGIApp
from pycraftcore.web.schema import ApiSettings

from bootstrap.application.fastapi.fastapi_api import create_fastapi_api
from bootstrap.configuration.settings import ProcessSettings
from bootstrap.container.agent_container import AgentContainer
from src import APPLICATION_VERSION


@asynccontextmanager
async def _lifespan(container: AgentContainer) -> AsyncGenerator[None]:
    try:
        await container.boot()
    except Exception as exception:
        container.logging.critical(
            "Agent container failed to boot:\n" + "".join(traceback.format_exception(exception))
        )
        raise

    try:
        yield
    finally:
        await container.stop()


def create_agent_application(settings: ProcessSettings | None = None) -> ASGIApp:
    process_settings = settings or ProcessSettings.for_role("agent-runtime")
    container = AgentContainer(process_settings)
    server = container.server

    api = ApiSettings(
        title=server.name,
        version=APPLICATION_VERSION,
        base_path=server.base_path,
        docs=server.docs,
        cors_origins=server.cors_origins,
    )
    return create_fastapi_api(
        api,
        lifespan=lambda: _lifespan(container),
        agent=lambda: container.stream_agent_controller,
        models=lambda: container.list_models,
        agents=lambda: container.list_agents,
        a2a_handler=container.a2a_request_handler,
        agent_card=container.a2a_agent_card,
        a2a_options=lambda: container.a2a_options,
        routes=container.agent.routes,
        actuator=container.actuator,
        logger=container.logging,
    )
