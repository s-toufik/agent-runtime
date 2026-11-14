import asyncio
from collections.abc import Callable

import aiosqlite
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pycraftcore.application_configuration import ApplicationConfiguration
from pycraftcore.application_configuration.model.connector import DatabaseConnector
from pycraftcore.logger.port import Logger
from pycraftcore.repository.adapter import (
    MongoRepositoryFactory,
    MongoSettingsMapper,
    PostgresEngineBuilder,
    PostgresSettingsMapper,
    SqlAlchemyRepositoryFactory,
    SqliteEngineBuilder,
    SqliteRepositoryFactory,
    SqliteSettingsMapper,
)
from pycraftcore.repository.port import AsyncRepositoryFactory
from pymongo import MongoClient
from sqlalchemy.ext.asyncio import AsyncEngine

MONGODB_CHECKPOINTER: str = "mongodb_checkpointer"
SQLITE_CHECKPOINTER: str = "sqlite_checkpointer"
POSTGRES_A2A_TASKS: str = "postgres_a2a_tasks"
SQLITE_A2A_TASKS: str = "sqlite_a2a_tasks"
DEFAULT_CHECKPOINT_TTL: int = 604800

Checkpointer = AsyncSqliteSaver | MongoDBSaver
Register = Callable[[AsyncRepositoryFactory], AsyncRepositoryFactory]


class StorageDI:
    def __init__(
        self,
        configuration: ApplicationConfiguration,
        logger: Logger,
        register: Register,
    ) -> None:
        self._configuration = configuration
        self._logger = logger
        self._register = register

    async def checkpointer(self) -> Checkpointer:
        mongo_saver: MongoDBSaver | None = await self._mongodb_checkpointer()
        if mongo_saver is not None:
            self._logger.info("Using MongoDB checkpointer with TTL")
            return mongo_saver

        self._logger.info("Using Sqlite checkpointer with no TTL")
        return AsyncSqliteSaver(await self._sqlite_connection(SQLITE_CHECKPOINTER))

    async def a2a_tasks_engine(self) -> AsyncEngine:
        engine: AsyncEngine | None = await self._postgres_engine(POSTGRES_A2A_TASKS)
        if engine is not None:
            self._logger.info("Storing A2A tasks in PostgreSQL")
            return engine

        self._logger.info("Storing A2A tasks in SQLite")
        settings = SqliteSettingsMapper(self._connector(SQLITE_A2A_TASKS))()
        return await self._engine(SqlAlchemyRepositoryFactory(SqliteEngineBuilder(settings)))

    async def _mongodb_checkpointer(self) -> MongoDBSaver | None:
        client: MongoClient | None = await self._mongo_client(MONGODB_CHECKPOINTER)
        if client is None:
            return None
        connector: DatabaseConnector = self._connector(MONGODB_CHECKPOINTER)
        return await asyncio.to_thread(
            MongoDBSaver,
            client,
            db_name=connector.default_name,
            ttl=connector.pool.get("ttl", DEFAULT_CHECKPOINT_TTL),
        )

    async def _mongo_client(self, name: str) -> MongoClient | None:
        factory = MongoRepositoryFactory(MongoSettingsMapper(self._connector(name))())
        self._register(factory)
        try:
            await factory.ping()
            return await factory.connection()
        except Exception as exception:
            self._logger.warning(f"MongoDB '{name}' unavailable: {exception}")
            await factory.disconnect()
            return None

    async def _sqlite_connection(self, name: str) -> aiosqlite.Connection:
        factory = SqliteRepositoryFactory(SqliteSettingsMapper(self._connector(name))())
        self._register(factory)
        return await factory.connection()

    async def _postgres_engine(self, name: str) -> AsyncEngine | None:
        connector: DatabaseConnector = self._connector(name)
        if not connector.host.strip():
            self._logger.info(f"PostgreSQL '{name}' has no host: not used")
            return None
        settings = PostgresSettingsMapper(connector)()
        factory = SqlAlchemyRepositoryFactory(PostgresEngineBuilder(settings))
        try:
            await factory.ping()
        except Exception as exception:
            self._logger.warning(f"PostgreSQL '{name}' unavailable: {exception}")
            await factory.disconnect()
            return None
        return await self._engine(factory)

    async def _engine(self, factory: SqlAlchemyRepositoryFactory) -> AsyncEngine:
        self._register(factory)
        return await factory.connection()

    def _connector(self, name: str) -> DatabaseConnector:
        return self._configuration.connector.database(name)
