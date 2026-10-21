from contextlib import AbstractContextManager
from typing import Protocol

from agent_runtime.domain.turn.token_usage import TokenUsage


class UsageScope(Protocol):
    def usage(self) -> TokenUsage | None: ...


class UsageMeter(Protocol):
    def measure(self) -> AbstractContextManager[UsageScope]: ...
