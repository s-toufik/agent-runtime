from pathlib import Path

import pytest

from bootstrap.configuration.settings import ProcessSettings
from bootstrap.di.agent_di import AgentDI
from tests.support.agents import TEST_AGENT, TEST_AGENTS

REAL_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"


def make_settings(guardrail_enabled: bool = False) -> ProcessSettings:
    return ProcessSettings(
        role="agent-runtime",
        environment="debug",
        configuration_directory=REAL_CONFIG_DIR,
        guardrail_enabled=guardrail_enabled,
        agent=TEST_AGENT,
        agents_directory=TEST_AGENTS,
    )


@pytest.fixture
def di() -> AgentDI:
    return AgentDI(make_settings())
