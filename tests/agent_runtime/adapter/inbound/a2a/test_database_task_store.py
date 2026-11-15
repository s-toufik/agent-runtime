from sqlalchemy.ext.asyncio import create_async_engine

from agent_runtime.adapter.inbound.a2a.database_task_store import database_task_store


def test_a_table_can_back_several_stores_in_one_process(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'tasks.db'}")

    first = database_task_store(engine, "tasks_reused")
    second = database_task_store(engine, "tasks_reused")

    assert first.task_model is second.task_model
    assert first.task_model.__tablename__ == "tasks_reused"


def test_the_sdk_s_own_table_keeps_its_model(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'tasks.db'}")

    assert database_task_store(engine, "tasks").task_model.__tablename__ == "tasks"
