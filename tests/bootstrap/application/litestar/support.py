from collections.abc import Callable

from litestar import Litestar
from pycraftcore.logger.port import Logger
from pycraftcore.web.actuator import Actuator
from pycraftcore.web.schema import ApiSettings

from agent_runtime.adapter.inbound.web.stream.stream_agent_controller import (
    StreamAgentController,
)
from agent_runtime.application.port.inbound.list_models_port import ListModelsPort
from bootstrap.application.litestar.litestar_api import create_litestar_api
from tests.support.web import nothing

ACTUATOR = Actuator("agent-runtime", "1.0.0", "test", "team@example.com", lambda: True)


def litestar_api(
    logger: Logger,
    agent: Callable[[], StreamAgentController],
    models: Callable[[], ListModelsPort],
) -> Litestar:
    return create_litestar_api(
        ApiSettings(title="agent-runtime"),
        lifespan=nothing,
        agent=agent,
        models=models,
        actuator=ACTUATOR,
        logger=logger,
    )
