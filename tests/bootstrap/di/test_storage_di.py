import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from sqlalchemy.ext.asyncio import AsyncEngine

from bootstrap.di.agent_di import AgentDI
from bootstrap.di.storage_di import StorageDI
from tests.bootstrap.di.conftest import make_settings


@pytest.fixture
def storage(di: AgentDI, logger) -> StorageDI:
    return StorageDI(di._configuration, logger, di._register_repository)


async def test_without_mongodb_the_conversation_goes_to_sqlite(di, storage, logger) -> None:
    checkpointer = await storage.checkpointer()

    assert isinstance(checkpointer, AsyncSqliteSaver)
    assert any("MongoDB" in message for message in logger.messages("warning"))
    await di._stop_factories()


async def test_without_a_postgresql_host_a2a_tasks_go_to_sqlite(
    di, storage, logger, tmp_path
) -> None:
    engine: AsyncEngine = await storage.a2a_tasks_engine()

    assert engine.url.drivername == "sqlite+aiosqlite"
    assert engine.url.database == str(tmp_path / "a2a_tasks.db")
    assert any("has no host" in message for message in logger.messages("info"))
    await di._stop_factories()


async def test_an_unreachable_postgresql_falls_back_to_sqlite(monkeypatch, logger) -> None:
    monkeypatch.setenv("DB_POSTGRES_A2A_HOST", "127.0.0.1")
    monkeypatch.setenv("DB_POSTGRES_A2A_PORT", "1")
    di = AgentDI(make_settings())
    storage = StorageDI(di._configuration, logger, di._register_repository)

    engine: AsyncEngine = await storage.a2a_tasks_engine()

    assert engine.url.drivername == "sqlite+aiosqlite"
    assert any(
        "PostgreSQL 'postgres_a2a_tasks' unavailable" in m for m in logger.messages("warning")
    )
    await di._stop_factories()


async def test_the_chosen_engine_is_registered_to_close_with_the_other_databases(
    di, storage
) -> None:
    before = len(di._repositories)

    await storage.a2a_tasks_engine()

    assert len(di._repositories) == before + 1
    await di._stop_factories()
