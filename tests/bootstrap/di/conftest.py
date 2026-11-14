from pathlib import Path

import pytest

from bootstrap.configuration.settings import ProcessSettings
from bootstrap.di.agent_di import AgentDI

REAL_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"


def make_settings(guardrail_enabled: bool = False) -> ProcessSettings:
    return ProcessSettings(
        role="agent-runtime",
        environment="debug",
        configuration_directory=REAL_CONFIG_DIR,
        guardrail_enabled=guardrail_enabled,
    )


@pytest.fixture
def di() -> AgentDI:
    return AgentDI(make_settings())
