import asyncio
from collections.abc import Callable
from dataclasses import dataclass

import aiosqlite
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pycraftcore.application_configuration import ApplicationConfiguration
from pycraftcore.application_configuration.model.operation import DatabaseOperation
from pycraftcore.logger.port import Logger
from pycraftcore.repository.adapter import (
    MongoRepositoryFactory,
    MongoSettingsMapper,
    MongoTtlIndex,
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

CONVERSATION_MONGODB: str = "conversation_mongodb"
CONVERSATION_SQLITE: str = "conversation_sqlite"
A2A_TASKS_POSTGRESQL: str = "a2a_tasks_postgresql"
A2A_TASKS_SQLITE: str = "a2a_tasks_sqlite"
CHECKPOINTS: str = "checkpoints"
WRITES: str = "writes"
CHECKPOINT_TTL_FIELD: str = "created_at"

Checkpointer = AsyncSqliteSaver | MongoDBSaver
Register = Callable[[AsyncRepositoryFactory], AsyncRepositoryFactory]


@dataclass(frozen=True, slots=True)
class A2aTaskStorage:
    engine: AsyncEngine
    operation: DatabaseOperation


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
        return AsyncSqliteSaver(await self._sqlite_connection(CONVERSATION_SQLITE))

    async def a2a_tasks(self) -> A2aTaskStorage:
        postgresql = self._operation(A2A_TASKS_POSTGRESQL)
        engine: AsyncEngine | None = await self._postgres_engine(postgresql)
        if engine is not None:
            self._logger.info("Storing A2A tasks in PostgreSQL")
            return A2aTaskStorage(engine, postgresql)

        self._logger.info("Storing A2A tasks in SQLite")
        sqlite = self._operation(A2A_TASKS_SQLITE)
        builder = SqliteEngineBuilder(SqliteSettingsMapper(sqlite)())
        return A2aTaskStorage(await self._engine(SqlAlchemyRepositoryFactory(builder)), sqlite)

    async def _mongodb_checkpointer(self) -> MongoDBSaver | None:
        operation = self._operation(CONVERSATION_MONGODB)
        client: MongoClient | None = await self._mongo_client(operation)
        if client is None:
            return None
        checkpoints, writes = operation.collection(CHECKPOINTS), operation.collection(WRITES)
        if operation.ttl is not None:
            ttl_index = MongoTtlIndex(CHECKPOINT_TTL_FIELD, operation.ttl)
            for collection in (checkpoints, writes):
                await ttl_index.ensure(client[operation.database][collection])
        return await asyncio.to_thread(
            MongoDBSaver,
            client,
            db_name=operation.database,
            checkpoint_collection_name=checkpoints,
            writes_collection_name=writes,
            ttl=operation.ttl,
        )

    async def _mongo_client(self, operation: DatabaseOperation) -> MongoClient | None:
        factory = MongoRepositoryFactory(MongoSettingsMapper(operation)())
        self._register(factory)
        try:
            await factory.ping()
            return await factory.connection()
        except Exception as exception:
            self._logger.warning(f"MongoDB '{operation.name}' unavailable: {exception}")
            await factory.disconnect()
            return None

    async def _sqlite_connection(self, name: str) -> aiosqlite.Connection:
        factory = SqliteRepositoryFactory(SqliteSettingsMapper(self._operation(name))())
        self._register(factory)
        return await factory.connection()

    async def _postgres_engine(self, operation: DatabaseOperation) -> AsyncEngine | None:
        if not operation.connector.host.strip():
            self._logger.info(f"PostgreSQL '{operation.name}' has no host: not used")
            return None
        settings = PostgresSettingsMapper(operation)()
        factory = SqlAlchemyRepositoryFactory(PostgresEngineBuilder(settings))
        try:
            await factory.ping()
        except Exception as exception:
            self._logger.warning(f"PostgreSQL '{operation.name}' unavailable: {exception}")
            await factory.disconnect()
            return None
        return await self._engine(factory)

    async def _engine(self, factory: SqlAlchemyRepositoryFactory) -> AsyncEngine:
        self._register(factory)
        return await factory.connection()

    def _operation(self, name: str) -> DatabaseOperation:
        return self._configuration.operation.database(name)
