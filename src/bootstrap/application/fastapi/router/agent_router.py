from collections.abc import Callable

from fastapi import APIRouter
from pycraftcore.web_fastapi import EventStreamResponse, event_stream

from agent_runtime.adapter.inbound.web.stream.stream_agent_controller import (
    StreamAgentController,
)
from agent_runtime.application.port.inbound.list_models_port import ListModelsPort
from bootstrap.application.fastapi.schema.agent_request_schema import AgentRequestSchema
from bootstrap.application.fastapi.schema.model_list_schema import ModelListSchema

AGENT_TAG: str = "Agent"


def agent_router(
    agent: Callable[[], StreamAgentController],
    models: Callable[[], ListModelsPort],
) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=[AGENT_TAG])

    @router.post("/stream", response_class=EventStreamResponse)
    async def stream(data: AgentRequestSchema) -> EventStreamResponse:
        return event_stream(await agent().execute(data.to_domain()))

    @router.get("/models")
    async def list_models() -> ModelListSchema:
        return ModelListSchema.from_domain(await models().handle())

    return router
