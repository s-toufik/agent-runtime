from collections.abc import Callable

from fastapi import APIRouter
from pycraftcore.web_fastapi import EventStreamResponse, event_stream

from agent_runtime.adapter.inbound.web.stream.stream_agent_controller import (
    StreamAgentController,
)
from agent_runtime.application.port.inbound.list_agents_port import ListAgentsPort
from agent_runtime.application.port.inbound.list_models_port import ListModelsPort
from agent_runtime.domain.agent.agent_routes import AgentRoutes
from bootstrap.application.fastapi.schema.agent_list_schema import AgentListSchema
from bootstrap.application.fastapi.schema.agent_request_schema import AgentRequestSchema
from bootstrap.application.fastapi.schema.model_list_schema import ModelListSchema

AGENT_TAG: str = "Agent"


MODELS_PATH: str = "/v1/models"
AGENTS_PATH: str = "/v1/agents"


def agent_router(
    agent: Callable[[], StreamAgentController],
    models: Callable[[], ListModelsPort],
    agents: Callable[[], ListAgentsPort],
    routes: AgentRoutes,
) -> APIRouter:
    router = APIRouter(tags=[AGENT_TAG])

    @router.post(routes.api2a, response_class=EventStreamResponse)
    async def api2a(data: AgentRequestSchema) -> EventStreamResponse:
        return event_stream(await agent().execute(data.to_domain()))

    @router.get(AGENTS_PATH)
    async def list_agents() -> AgentListSchema:
        return AgentListSchema.from_domain(await agents().handle())

    @router.get(MODELS_PATH)
    async def list_models() -> ModelListSchema:
        return ModelListSchema.from_domain(await models().handle())

    return router
