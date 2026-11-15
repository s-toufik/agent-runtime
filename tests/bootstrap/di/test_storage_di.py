import pytest
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pycraftcore.repository.adapter.no_sql.mongodb import factory as mongo_factory
from pymongo.errors import OperationFailure

from bootstrap.di.agent_di import AgentDI
from bootstrap.di.storage_di import StorageDI
from tests.bootstrap.di.conftest import make_settings
from tests.support.mongo import FakeMongoClient

HOUR = 3600
WEEK = 604800


@pytest.fixture
def storage(di: AgentDI, logger) -> StorageDI:
    return StorageDI(di._configuration, logger, di._register_repository)


async def test_without_mongodb_the_conversation_goes_to_sqlite(di, storage, logger) -> None:
    checkpointer = await storage.checkpointer()

    assert isinstance(checkpointer, AsyncSqliteSaver)
    assert any("MongoDB" in message for message in logger.messages("warning"))
    await di._stop_factories()


@pytest.fixture
def mongodb(monkeypatch) -> FakeMongoClient:
    client = FakeMongoClient()
    monkeypatch.setattr(mongo_factory, "MongoClient", lambda *args, **kwargs: client)
    return client


async def test_a_reachable_mongodb_keeps_the_conversation_for_the_configured_ttl(
    di, storage, mongodb
) -> None:
    checkpointer = await storage.checkpointer()

    assert isinstance(checkpointer, MongoDBSaver)
    database = mongodb["checkpoint"]
    assert database["checkpoints"].ttl() == WEEK
    assert database["checkpoint_writes"].ttl() == WEEK
    await di._stop_factories()


async def test_a_ttl_changed_since_the_indexes_were_created_no_longer_stops_the_boot(
    di, storage, mongodb
) -> None:
    database = mongodb["checkpoint"]
    for name in ("checkpoints", "checkpoint_writes"):
        database[name].create_index([("created_at", 1)], expireAfterSeconds=HOUR)

    checkpointer = await storage.checkpointer()

    assert isinstance(checkpointer, MongoDBSaver)
    assert database["checkpoints"].ttl() == WEEK
    assert database["checkpoint_writes"].ttl() == WEEK
    await di._stop_factories()


def test_the_fake_mongodb_refuses_another_ttl_as_the_server_did(mongodb) -> None:
    collection = mongodb["checkpoint"]["checkpoints"]
    collection.create_index([("created_at", 1)], expireAfterSeconds=HOUR)

    with pytest.raises(OperationFailure):
        MongoDBSaver(mongodb, db_name="checkpoint", ttl=WEEK)


async def test_without_a_postgresql_host_a2a_tasks_go_to_sqlite(
    di, storage, logger, tmp_path
) -> None:
    tasks = await storage.a2a_tasks()

    assert tasks.engine.url.drivername == "sqlite+aiosqlite"
    assert tasks.engine.url.database == str(tmp_path / "a2a_tasks.db")
    assert tasks.operation.name == "a2a_tasks_sqlite"
    assert (tasks.operation.collection("tasks"), tasks.operation.ttl) == ("tasks", 604800)
    assert any("has no host" in message for message in logger.messages("info"))
    await di._stop_factories()


async def test_an_unreachable_postgresql_falls_back_to_sqlite(monkeypatch, logger) -> None:
    monkeypatch.setenv("DB_POSTGRES_A2A_HOST", "127.0.0.1")
    monkeypatch.setenv("DB_POSTGRES_A2A_PORT", "1")
    di = AgentDI(make_settings())
    storage = StorageDI(di._configuration, logger, di._register_repository)

    tasks = await storage.a2a_tasks()

    assert tasks.engine.url.drivername == "sqlite+aiosqlite"
    assert any(
        "PostgreSQL 'a2a_tasks_postgresql' unavailable" in m for m in logger.messages("warning")
    )
    await di._stop_factories()


async def test_the_a2a_task_ttl_comes_from_the_environment(monkeypatch, logger) -> None:
    monkeypatch.setenv("A2A_TASK_TTL", "3600")
    di = AgentDI(make_settings())
    storage = StorageDI(di._configuration, logger, di._register_repository)

    tasks = await storage.a2a_tasks()

    assert tasks.operation.ttl == 3600
    await di._stop_factories()


async def test_each_agent_can_keep_its_tasks_in_its_own_table(monkeypatch, logger) -> None:
    monkeypatch.setenv("A2A_TASKS_TABLE", "tasks_chat")
    di = AgentDI(make_settings())
    storage = StorageDI(di._configuration, logger, di._register_repository)

    tasks = await storage.a2a_tasks()

    assert tasks.operation.collection("tasks") == "tasks_chat"
    await di._stop_factories()


async def test_the_chosen_engine_is_registered_to_close_with_the_other_databases(
    di, storage
) -> None:
    before = len(di._repositories)

    await storage.a2a_tasks()

    assert len(di._repositories) == before + 1
    await di._stop_factories()
