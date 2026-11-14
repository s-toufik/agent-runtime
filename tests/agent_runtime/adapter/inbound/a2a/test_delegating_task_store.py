import pytest
from a2a.server.context import ServerCallContext
from a2a.server.tasks import InMemoryTaskStore
from a2a.types.a2a_pb2 import ListTasksRequest, Task, TaskState, TaskStatus

from agent_runtime.adapter.inbound.a2a.delegating_task_store import DelegatingTaskStore

CONTEXT = ServerCallContext()
TASK = Task(id="t1", context_id="c1", status=TaskStatus(state=TaskState.TASK_STATE_COMPLETED))


async def test_every_call_reaches_the_store_it_is_given() -> None:
    target = InMemoryTaskStore()
    store = DelegatingTaskStore(lambda: target)

    await store.save(TASK, CONTEXT)
    listed = await store.list(ListTasksRequest(), CONTEXT)
    await store.delete("t1", CONTEXT)

    assert [task.id for task in listed.tasks] == ["t1"]
    assert await target.get("t1", CONTEXT) is None


async def test_the_store_is_asked_for_at_each_call_not_when_built() -> None:
    stores: list[InMemoryTaskStore] = []
    store = DelegatingTaskStore(lambda: stores[-1])
    stores.append(InMemoryTaskStore())

    await store.save(TASK, CONTEXT)

    assert await stores[0].get("t1", CONTEXT) is not None


async def test_a_store_that_is_not_ready_says_so() -> None:
    def not_booted():
        raise RuntimeError("The agent container is not booted")

    with pytest.raises(RuntimeError, match="not booted"):
        await DelegatingTaskStore(not_booted).get("t1", CONTEXT)
