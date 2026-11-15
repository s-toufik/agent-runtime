from typing import Protocol

from agent_runtime.domain.a2a.turn_options import TurnOptions


class DescribeA2aOptionsPort(Protocol):
    async def handle(self) -> TurnOptions: ...
