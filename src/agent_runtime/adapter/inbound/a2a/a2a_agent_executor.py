import asyncio
from collections.abc import Callable
from contextlib import aclosing
from typing import Any

from a2a.helpers import new_task_from_user_message, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types.a2a_pb2 import Message, Task
from google.protobuf import json_format
from pycraftcore.context.request_id_context import request_id_context
from pycraftcore.logger.port import Logger

from agent_runtime.adapter.inbound.a2a.a2a_task_presenter import A2aTaskPresenter
from agent_runtime.application.port.inbound.run_a2a_task_port import RunA2aTaskPort
from agent_runtime.domain.a2a.a2a_task_request import A2aTaskRequest

TEXT_ONLY: str = "Only text parts are supported."
AT_CAPACITY: str = "Server is at capacity, please retry."


class A2aAgentExecutor(AgentExecutor):
    def __init__(
        self,
        run_task: Callable[[], RunA2aTaskPort],
        logger: Logger,
        *,
        max_concurrent_turns: int = 200,
        presenter: A2aTaskPresenter | None = None,
    ) -> None:
        self._run_task = run_task
        self._logger = logger
        self._admission = asyncio.Semaphore(max_concurrent_turns)
        self._presenter = presenter or A2aTaskPresenter()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task: Task = await _task(context, event_queue)
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        request_id_context.set(task.context_id)

        text: str = context.get_user_input().strip()
        if not text:
            await updater.reject(updater.new_agent_message([new_text_part(TEXT_ONLY)]))
            return
        if self._admission.locked():
            self._logger.warning("a2a rejected: server at capacity")
            await updater.failed(updater.new_agent_message([new_text_part(AT_CAPACITY)]))
            return

        async with self._admission:
            self._logger.info(f"a2a task {task.id} started")
            await updater.start_work()
            request = _request(context, text, task.context_id)
            async with aclosing(self._run_task().run(request)) as updates:
                async for update in updates:
                    await self._presenter.present(updater, update)
            self._logger.info(f"a2a task {task.id} ended")

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id or "", context.context_id or "")
        await updater.cancel()
        self._logger.info(f"a2a task {context.task_id} canceled")


async def _task(context: RequestContext, event_queue: EventQueue) -> Task:
    if context.current_task is not None:
        return context.current_task
    message: Message = context.message or Message()
    task: Task = new_task_from_user_message(message)
    await event_queue.enqueue_event(task)
    return task


def _request(context: RequestContext, text: str, context_id: str) -> A2aTaskRequest:
    message_metadata: dict[str, Any] = (
        json_format.MessageToDict(context.message.metadata) if context.message else {}
    )
    metadata: dict[str, Any] = {**context.metadata, **message_metadata}
    model: Any = metadata.get("model")
    return A2aTaskRequest(
        text=text,
        context_id=context_id,
        model_name=model if isinstance(model, str) else "",
        auto_approve=metadata.get("autoApprove") is True,
    )
