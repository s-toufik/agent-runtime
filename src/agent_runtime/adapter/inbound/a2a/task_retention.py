import asyncio
from datetime import UTC, datetime, timedelta

from a2a.server.models import TaskModel
from pycraftcore.logger.port import Logger
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine

PURGE_INTERVAL: timedelta = timedelta(hours=1)


class TaskRetention:
    def __init__(
        self,
        engine: AsyncEngine,
        task_model: type[TaskModel],
        ttl: timedelta,
        logger: Logger,
        interval: timedelta = PURGE_INTERVAL,
    ) -> None:
        self._engine = engine
        self._task_model = task_model
        self._ttl = ttl
        self._logger = logger
        self._interval = interval

    async def purge(self) -> int:
        cutoff: datetime = datetime.now(UTC).replace(tzinfo=None) - self._ttl
        async with self._engine.begin() as connection:
            result = await connection.execute(
                delete(self._task_model).where(self._task_model.last_updated < cutoff)
            )
        return result.rowcount

    async def run(self) -> None:
        while True:
            try:
                removed: int = await self.purge()
                if removed:
                    self._logger.info(f"Removed {removed} A2A tasks older than {self._ttl}")
            except Exception as exception:
                self._logger.warning(f"A2A task cleanup failed: {exception}")
            await asyncio.sleep(self._interval.total_seconds())
