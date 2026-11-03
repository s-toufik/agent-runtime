from litestar import Controller, get, post
from litestar.params import JSONBody, SkipValidation
from litestar.response import Stream
from pycraftcore.web.sse import EVENT_STREAM_MEDIA_TYPE
from pycraftcore.web_litestar import event_stream

from agent_runtime.adapter.inbound.web.stream.stream_agent_controller import (
    StreamAgentController,
)
from agent_runtime.application.port.inbound.list_models_port import ListModelsPort
from bootstrap.application.litestar.schema.agent_request_schema import (
    AgentRequestSchema,
)
from bootstrap.application.litestar.schema.model_list_schema import ModelListSchema


class AgentRouter(Controller):
    path = "/v1"

    @post("/stream", status_code=200, media_type=EVENT_STREAM_MEDIA_TYPE)
    async def stream(
        self,
        data: JSONBody[AgentRequestSchema],
        agent: SkipValidation[StreamAgentController],
    ) -> Stream:
        return event_stream(await agent.execute(data.to_domain()))

    @get("/models")
    async def list_models(self, models: SkipValidation[ListModelsPort]) -> ModelListSchema:
        return ModelListSchema.from_domain(await models.handle())
