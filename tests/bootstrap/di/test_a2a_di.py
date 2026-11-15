from datetime import timedelta

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks.database_task_store import DatabaseTaskStore
from pycraftcore.application_configuration.enum import ConnectorType
from pycraftcore.application_configuration.enum.operation_type import OperationType
from pycraftcore.application_configuration.model.connector import DatabaseConnector
from pycraftcore.application_configuration.model.operation import DatabaseOperation
from pycraftcore.authentication.model.no_auth import NoAuth
from sqlalchemy.ext.asyncio import create_async_engine

from agent_runtime.adapter.inbound.a2a.task_retention import TaskRetention
from agent_runtime.adapter.outbound.llm.enum.answer_delivery import AnswerDelivery
from bootstrap.configuration.a2a_settings import A2aSettings
from bootstrap.configuration.server_parameters import ServerParameters
from bootstrap.di.a2a_di import A2aDI
from bootstrap.di.storage_di import A2aTaskStorage
from tests.support.agents import AGENT

PARAMETERS = ServerParameters(max_concurrent_streams=3, answer_delivery=AnswerDelivery.STREAM)
SETTINGS = A2aSettings(url="https://agent.example/a2a")


def _a2a(logger) -> A2aDI:
    def not_booted():
        raise RuntimeError("not booted")

    return A2aDI(
        AGENT,
        "1.2.3",
        PARAMETERS,
        SETTINGS,
        logger,
        run_task=not_booted,
        task_store=not_booted,
    )


def _storage(table: str = "tasks", ttl: int | None = 3600) -> A2aTaskStorage:
    connector = DatabaseConnector(
        name="sqlite", type=ConnectorType.database, auth=NoAuth(), engine="sqlite", host="", port=0
    )
    operation = DatabaseOperation(
        name="a2a_tasks_sqlite",
        type=OperationType.database,
        connector=connector,
        database="a2a_tasks",
        collections={"tasks": table},
        ttl=ttl,
    )
    return A2aTaskStorage(create_async_engine("sqlite+aiosqlite://"), operation)


async def _tables(storage: A2aTaskStorage) -> set[str]:
    async with storage.engine.connect() as connection:
        rows = await connection.exec_driver_sql("SELECT name FROM sqlite_master")
        return {row[0] for row in rows}


def test_the_card_announces_the_configured_url(logger) -> None:
    card = _a2a(logger).card

    assert (card.name, card.version) == ("agent-runtime", "1.2.3")
    assert card.supported_interfaces[0].url == "https://agent.example/a2a"


def test_the_request_handler_is_built_without_any_database(logger) -> None:
    a2a = _a2a(logger)

    assert isinstance(a2a.request_handler, DefaultRequestHandler)
    assert a2a.request_handler is a2a.request_handler


async def test_the_task_store_creates_the_table_its_operation_names(logger) -> None:
    storage = _storage(table="a2a_task")

    store = await _a2a(logger).task_store(storage)

    assert isinstance(store, DatabaseTaskStore)
    assert "a2a_task" in await _tables(storage)
    await storage.engine.dispose()


async def test_the_retention_purges_that_table_after_the_operation_s_ttl(logger) -> None:
    storage = _storage(table="purged_a2a_task")
    a2a = _a2a(logger)
    store = await a2a.task_store(storage)

    retention = a2a.retention(store, storage)

    assert isinstance(retention, TaskRetention)
    assert retention._ttl == timedelta(hours=1)
    assert await retention.purge() == 0
    await storage.engine.dispose()


async def test_without_a_ttl_tasks_are_kept_and_nothing_purges_them(logger) -> None:
    storage = _storage(ttl=None)
    a2a = _a2a(logger)

    assert a2a.retention(await a2a.task_store(storage), storage) is None
    assert any("have no ttl" in message for message in logger.messages("info"))
    await storage.engine.dispose()
