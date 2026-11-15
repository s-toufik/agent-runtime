import asyncio
from collections.abc import AsyncGenerator, Callable

from agent_runtime.application.port.inbound.handle_message_port import HandleMessagePort
from agent_runtime.application.port.inbound.list_models_port import ListModelsPort
from agent_runtime.application.port.outbound.turn_event_stream import TurnEventStream
from agent_runtime.application.use_case.describe_a2a_options import DescribeA2aOptions
from agent_runtime.domain.a2a.a2a_task_request import A2aTaskRequest
from agent_runtime.domain.a2a.task_update import TaskUpdate
from agent_runtime.domain.request.agent_request import AgentRequest


class RunA2aTask:
    def __init__(
        self,
        handle_message: HandleMessagePort,
        stream_events: Callable[[], TurnEventStream],
        models: ListModelsPort,
    ) -> None:
        self._handle_message = handle_message
        self._stream_events = stream_events
        self._options = DescribeA2aOptions(models)

    async def run(self, request: A2aTaskRequest) -> AsyncGenerator[TaskUpdate]:
        message = AgentRequest(
            request.text, await self._model_for(request), request.context_id, request.auto_approve
        )
        events: TurnEventStream = self._stream_events()
        turn: asyncio.Task[None] = asyncio.create_task(self._handle_message.handle(message, events))
        ended: bool = False
        try:
            async for event in events:
                update = TaskUpdate.after(event)
                ended = ended or update.state.ends_the_turn
                yield update
            if not ended:
                yield TaskUpdate.unanswered()
        finally:
            await _cancel(turn)

    async def _model_for(self, request: A2aTaskRequest) -> str:
        if request.model_name:
            return request.model_name
        options = await self._options.handle()
        return options.default_model


async def _cancel(task: asyncio.Task[None]) -> None:
    if task.done():
        return
    task.cancel()
    try:
        await task
    except BaseException:
        pass
