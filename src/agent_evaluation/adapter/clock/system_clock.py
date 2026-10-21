import asyncio
import logging
import time
from datetime import datetime

logger: logging.Logger = logging.getLogger(__name__)


class SystemClock:
    def now(self) -> datetime:
        return datetime.now().astimezone()

    def monotonic(self) -> float:
        return time.monotonic()

    async def sleep(self, seconds: float) -> None:
        if seconds <= 0:
            return
        logger.debug(f"pause {seconds:g}s")
        await asyncio.sleep(seconds)
