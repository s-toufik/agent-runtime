from pathlib import Path

import pytest
from pycraftcore.application_configuration.adapter import LoadApplicationConfiguration

from bootstrap.configuration.application_configuration import SetApplicationConfiguration
from bootstrap.configuration.settings import ProcessSettings

REAL_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"


def make_settings(directory: Path) -> ProcessSettings:
    return ProcessSettings(environment="debug", configuration_directory=directory)


def test_loads_the_real_configuration_tree(logger) -> None:

    configuration = SetApplicationConfiguration(make_settings(REAL_CONFIG_DIR), logger)()

    assert configuration.connector.mcp("toolbox").transport == "streamable_http"
    assert configuration.connector.database("sqlite").engine == "sqlite"
    assert configuration.connector.database("mongodb").engine == "mongodb"
    conversation = configuration.operation.database("conversation_mongodb")
    assert conversation.connector == configuration.connector.database("mongodb")
    assert conversation.collection("writes") == "checkpoint_writes"
    for name in ("conversation_sqlite", "a2a_tasks_postgresql", "a2a_tasks_sqlite"):
        assert configuration.operation.database(name).database
    assert configuration.operation.a2a("a2a").connector.binding == "JSONRPC"


def test_raises_when_the_configuration_directory_does_not_exist(logger, tmp_path) -> None:
    missing = tmp_path / "does-not-exist"

    with pytest.raises(FileNotFoundError):
        SetApplicationConfiguration(make_settings(missing), logger)()

    assert logger.messages("critical")


def test_raises_a_value_error_when_the_loader_returns_nothing(logger, monkeypatch) -> None:
    monkeypatch.setattr(LoadApplicationConfiguration, "load", lambda self: None)

    with pytest.raises(ValueError, match="No configuration loaded"):
        SetApplicationConfiguration(make_settings(REAL_CONFIG_DIR), logger)()


def test_uses_a_default_stdlib_logger_when_none_given() -> None:

    configuration = SetApplicationConfiguration(make_settings(REAL_CONFIG_DIR))()

    assert configuration is not None
