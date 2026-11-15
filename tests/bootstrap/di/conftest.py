from pathlib import Path

import pytest

from bootstrap.configuration.settings import ProcessSettings
from bootstrap.di.agent_di import AgentDI
from tests.support.agents import TEST_AGENT, TEST_AGENTS

REAL_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"


def make_settings(agent: str = TEST_AGENT) -> ProcessSettings:
    return ProcessSettings(
        environment="debug",
        configuration_directory=REAL_CONFIG_DIR,
        agent=agent,
        agents_directory=TEST_AGENTS,
    )


@pytest.fixture
def di() -> AgentDI:
    return AgentDI(make_settings())
