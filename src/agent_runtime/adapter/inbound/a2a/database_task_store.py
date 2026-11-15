from typing import Any

from a2a.server.models import TaskModel, create_task_model
from a2a.server.tasks.database_task_store import DatabaseTaskStore
from sqlalchemy.ext.asyncio import AsyncEngine

SDK_TABLE: str = "tasks"
_TASK_MODELS: dict[str, Any] = {SDK_TABLE: TaskModel}


def database_task_store(engine: AsyncEngine, table: str) -> DatabaseTaskStore:
    store = DatabaseTaskStore(engine, table_name=SDK_TABLE)
    store.task_model = _task_model(table)
    return store


def _task_model(table: str) -> Any:
    if table not in _TASK_MODELS:
        _TASK_MODELS[table] = create_task_model(table)
    return _TASK_MODELS[table]
