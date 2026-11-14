import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from tests.support.environment import apply_test_environment
from tests.support.tracing import install_recording_provider


def pytest_configure(config: pytest.Config) -> None:
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"


class FakeLogger:
    def __init__(self) -> None:
        self.records: list[tuple[str, str]] = []

    def _log(self, level: str, message: str) -> None:
        self.records.append((level, message))

    def info(self, message: str) -> None:
        self._log("info", message)

    def warning(self, message: str) -> None:
        self._log("warning", message)

    def error(self, message: str) -> None:
        self._log("error", message)

    def critical(self, message: str) -> None:
        self._log("critical", message)

    def debug(self, message: str) -> None:
        self._log("debug", message)

    def exception(self, message: str) -> None:
        self._log("exception", message)

    def messages(self, level: str) -> list[str]:
        return [message for recorded, message in self.records if recorded == level]


@pytest.fixture
def logger() -> FakeLogger:
    return FakeLogger()


@pytest.fixture
def anyio_backend() -> Any:
    return "asyncio"


@pytest.fixture(autouse=True)
def _test_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    apply_test_environment(monkeypatch, tmp_path)


@pytest.fixture(autouse=True)
def _fake_mongo_client(monkeypatch):
    from pycraftcore.repository.adapter.no_sql.mongodb import factory as mongo_factory

    class _UnreachableMongoClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        @property
        def admin(self):
            raise ConnectionError("no MongoDB available in tests")

        def close(self) -> None:
            pass

    monkeypatch.setattr(mongo_factory, "MongoClient", _UnreachableMongoClient)


@pytest.fixture(autouse=True)
def _null_telemetry(monkeypatch):
    from bootstrap.di import base_di
    from tests.support.null_telemetry import NullTelemetryProvider

    monkeypatch.setattr(base_di, "OpenTelemetryProvider", NullTelemetryProvider)


@pytest.fixture(autouse=True, scope="session")
def _isolate_global_tracer_provider() -> Iterator[InMemorySpanExporter]:
    import opentelemetry.trace as otel_trace

    exporter = install_recording_provider()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(otel_trace, "set_tracer_provider", lambda provider: None)
        yield exporter


@pytest.fixture
def spans(_isolate_global_tracer_provider: InMemorySpanExporter) -> Iterator[InMemorySpanExporter]:
    _isolate_global_tracer_provider.clear()
    yield _isolate_global_tracer_provider
    _isolate_global_tracer_provider.clear()
