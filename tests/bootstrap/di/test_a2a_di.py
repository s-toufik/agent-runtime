from datetime import timedelta

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks.database_task_store import DatabaseTaskStore
from sqlalchemy.ext.asyncio import create_async_engine

from agent_runtime.adapter.inbound.a2a.task_retention import TaskRetention
from agent_runtime.adapter.outbound.llm.enum.answer_delivery import AnswerDelivery
from agent_runtime.domain.a2a.agent_profile import AgentProfile
from bootstrap.configuration.server_parameters import ServerParameters
from bootstrap.di.a2a_di import A2aDI

PARAMETERS = ServerParameters(
    max_concurrent_streams=3,
    answer_delivery=AnswerDelivery.STREAM,
    a2a_url="https://agent.example/a2a",
    a2a_task_ttl=3600,
)


def _a2a(logger) -> A2aDI:
    def not_booted():
        raise RuntimeError("not booted")

    return A2aDI(
        AgentProfile("agent-runtime", "1.2.3"),
        PARAMETERS,
        logger,
        run_task=not_booted,
        task_store=not_booted,
    )


def test_the_card_announces_the_configured_url(logger) -> None:
    card = _a2a(logger).card

    assert (card.name, card.version) == ("agent-runtime", "1.2.3")
    assert card.supported_interfaces[0].url == "https://agent.example/a2a"


def test_the_request_handler_is_built_without_any_database(logger) -> None:
    a2a = _a2a(logger)

    assert isinstance(a2a.request_handler, DefaultRequestHandler)
    assert a2a.request_handler is a2a.request_handler


async def test_the_task_store_creates_its_table_on_the_engine(logger) -> None:
    engine = create_async_engine("sqlite+aiosqlite://")

    store = await _a2a(logger).task_store(engine)

    assert isinstance(store, DatabaseTaskStore)
    async with engine.connect() as connection:
        rows = await connection.exec_driver_sql("SELECT name FROM sqlite_master")
        assert "tasks" in {row[0] for row in rows}
    await engine.dispose()


def test_the_retention_keeps_tasks_for_the_configured_ttl(logger) -> None:
    retention = _a2a(logger).retention(create_async_engine("sqlite+aiosqlite://"))

    assert isinstance(retention, TaskRetention)
    assert retention._ttl == timedelta(hours=1)
