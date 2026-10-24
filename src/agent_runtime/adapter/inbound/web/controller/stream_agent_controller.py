import asyncio
import traceback
from asyncio import Task
from collections.abc import AsyncGenerator, Callable

from pycraftcore.context.request_id_context import request_id_context
from pycraftcore.logger.port import Logger
from pycraftcore.web.sse import with_heartbeat

from agent_runtime.adapter.inbound.web.exception.server_at_capacity_exception import (
    ServerAtCapacityException,
)
from agent_runtime.adapter.inbound.web.schema.agent_request_schema import AgentRequestSchema
from agent_runtime.adapter.inbound.web.sse_presenter import SsePresenter
from agent_runtime.application.port.inbound.handle_message_port import HandleMessagePort
from agent_runtime.application.port.outbound.turn_event_stream import TurnEventStream


class StreamAgentController:
    def __init__(
        self,
        use_case: HandleMessagePort,
        stream_events: Callable[[], TurnEventStream],
        logger: Logger,
        max_concurrent_streams: int = 200,
        presenter: SsePresenter | None = None,
        heartbeat_seconds: float | None = 15.0,
    ) -> None:
        self._use_case = use_case
        self._stream_events = stream_events
        self._logger = logger
        self._admission = asyncio.Semaphore(max_concurrent_streams)
        self._presenter = presenter or SsePresenter()
        self._heartbeat_seconds = heartbeat_seconds

    async def execute(self, request: AgentRequestSchema) -> AsyncGenerator[bytes]:
        if request.request_id:
            request_id_context.set(request.request_id)

        if self._admission.locked():
            self._logger.warning("rejected: server at capacity")
            raise ServerAtCapacityException("Server is at capacity, please retry.")

        await self._admission.acquire()

        try:
            self._logger.info("stream request accepted")
            events: TurnEventStream = self._stream_events()
            use_case_task: Task[None] = asyncio.create_task(
                self._use_case.handle(request.to_domain(), events)
            )
        except Exception:
            self._admission.release()
            raise

        return with_heartbeat(self._frames(request, events, use_case_task), self._heartbeat_seconds)

    async def _frames(
        self,
        request: AgentRequestSchema,
        events: TurnEventStream,
        use_case_task: Task[None],
    ) -> AsyncGenerator[bytes]:
        try:
            async for event in events:
                for chunk in self._presenter.present(event, request.request_id):
                    yield chunk
            yield self._presenter.complete()

        except asyncio.CancelledError, GeneratorExit:
            self._logger.warning("stream cancelled by the client")
            raise
        except Exception as exception:
            trace: str = "".join(traceback.format_exception(exception))
            self._logger.error(f"unhandled streaming error:\n{trace}")
            yield self._presenter.error(trace)
            raise
        finally:
            await self._cancel(use_case_task)
            self._admission.release()

    @staticmethod
    async def _cancel(task: Task[None]) -> None:
        if task.done():
            return
        task.cancel()
        try:
            await task
        except BaseException:
            pass
