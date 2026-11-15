import asyncio
from datetime import UTC, datetime, timedelta

from a2a.server.context import ServerCallContext
from a2a.server.tasks.database_task_store import DatabaseTaskStore
from a2a.types.a2a_pb2 import Task, TaskState, TaskStatus
from google.protobuf.timestamp_pb2 import Timestamp
from sqlalchemy.ext.asyncio import create_async_engine

from agent_runtime.adapter.inbound.a2a.task_retention import TaskRetention

CONTEXT = ServerCallContext()


def _task(task_id: str, age: timedelta) -> Task:
    timestamp = Timestamp()
    timestamp.FromDatetime(datetime.now(UTC) - age)
    status = TaskStatus(state=TaskState.TASK_STATE_COMPLETED, timestamp=timestamp)
    return Task(id=task_id, context_id="c1", status=status)


async def _store(*tasks: Task):
    engine = create_async_engine("sqlite+aiosqlite://")
    store = DatabaseTaskStore(engine)
    for task in tasks:
        await store.save(task, CONTEXT)
    return engine, store


async def test_tasks_older_than_the_ttl_are_removed_and_newer_ones_kept(logger) -> None:
    engine, store = await _store(
        _task("old", timedelta(days=8)), _task("recent", timedelta(days=1))
    )

    removed = await TaskRetention(engine, store.task_model, timedelta(days=7), logger).purge()

    assert removed == 1
    assert await store.get("old", CONTEXT) is None
    assert await store.get("recent", CONTEXT) is not None
    await engine.dispose()


async def test_the_cleanup_keeps_running_after_a_failure(logger) -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    retention = TaskRetention(
        engine,
        DatabaseTaskStore(engine).task_model,
        timedelta(days=7),
        logger,
        interval=timedelta(0),
    )

    running = asyncio.create_task(retention.run())
    while len(logger.messages("warning")) < 2:
        await asyncio.sleep(0.01)
    running.cancel()

    assert all("cleanup failed" in message for message in logger.messages("warning"))
    await engine.dispose()
