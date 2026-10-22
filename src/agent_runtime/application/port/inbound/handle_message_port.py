from typing import Protocol

from agent_runtime.application.port.outbound.turn_event_stream import TurnEventStream
from agent_runtime.domain.request.agent_request import AgentRequest

AGENT_UNAVAILABLE_MESSAGE: str = (
    "The assistant is temporarily unavailable due to repeated upstream "
    "failures/maintenance/unavailable resources. Please try again in a moment."
)
UNKNOWN_MODEL_MESSAGE: str = "{reason}: pick one of the available models."
MODEL_REJECTED_MESSAGE: str = (
    "The model server rejected the request ({reason}). Check the model configuration."
)


class HandleMessagePort(Protocol):
    async def handle(self, request: AgentRequest, events: TurnEventStream) -> None: ...
