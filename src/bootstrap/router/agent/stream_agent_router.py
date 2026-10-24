from pycraftcore.web.schema import HttpRoute, ResponseKind

from agent_runtime.adapter.inbound.web.controller.stream_agent_controller import (
    StreamAgentController,
)
from agent_runtime.adapter.inbound.web.schema.agent_request_schema import AgentRequestSchema


class StreamAgentRouter:
    PREFIX: str = "/v1"
    ENDPOINT: str = "/stream"

    def __init__(self, controller: StreamAgentController) -> None:
        self._controller = controller

    @property
    def routes(self) -> list[HttpRoute]:
        return [
            HttpRoute(
                method="POST",
                path=self.PREFIX + self.ENDPOINT,
                handler=self._controller.execute,
                body=AgentRequestSchema,
                kind=ResponseKind.EVENT_STREAM,
            )
        ]
