from collections.abc import Callable

from a2a.server.context import ServerCallContext
from a2a.server.tasks import TaskStore
from a2a.types.a2a_pb2 import ListTasksRequest, ListTasksResponse, Task


class DelegatingTaskStore(TaskStore):
    def __init__(self, store: Callable[[], TaskStore]) -> None:
        self._store = store

    async def save(self, task: Task, context: ServerCallContext) -> None:
        await self._store().save(task, context)

    async def get(self, task_id: str, context: ServerCallContext) -> Task | None:
        return await self._store().get(task_id, context)

    async def list(self, params: ListTasksRequest, context: ServerCallContext) -> ListTasksResponse:
        return await self._store().list(params, context)

    async def delete(self, task_id: str, context: ServerCallContext) -> None:
        await self._store().delete(task_id, context)
