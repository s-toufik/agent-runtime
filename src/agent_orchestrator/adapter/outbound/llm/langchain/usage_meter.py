from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from langchain_core.callbacks import get_usage_metadata_callback

from agent_orchestrator.domain.turn.token_usage import TokenUsage


class _LangChainUsageScope:
    def __init__(self, callback: Any) -> None:
        self._callback = callback

    def usage(self) -> TokenUsage | None:
        totals: dict[str, Any] = getattr(self._callback, "usage_metadata", None) or {}
        usage: TokenUsage = TokenUsage(
            input_tokens=sum(int(entry.get("input_tokens", 0)) for entry in totals.values()),
            output_tokens=sum(int(entry.get("output_tokens", 0)) for entry in totals.values()),
            total_tokens=sum(int(entry.get("total_tokens", 0)) for entry in totals.values()),
        )
        return None if usage.is_empty else usage


class LangChainUsageMeter:
    @contextmanager
    def measure(self) -> Generator[_LangChainUsageScope]:
        with get_usage_metadata_callback() as callback:
            yield _LangChainUsageScope(callback)
