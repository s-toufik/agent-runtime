from pycraftcore.application_configuration.enum import ConnectorType
from pycraftcore.application_configuration.model.connector import A2aConnector
from pycraftcore.authentication.model.no_auth import NoAuth

from bootstrap.configuration.peer_connectors import peer_connectors, peer_url_variable

TEMPLATE = A2aConnector(
    name="agent_peer", type=ConnectorType.a2a, auth=NoAuth(), base_url="", timeout=600
)


def test_each_peer_gets_the_template_and_the_url_of_its_variable() -> None:
    connectors = peer_connectors(
        TEMPLATE,
        ["observation", "kitchen"],
        {"AGENT_OBSERVATION_URL": " http://agent-observation:8000 "},
    )

    observation, kitchen = connectors["observation"], connectors["kitchen"]
    assert (observation.name, observation.base_url, observation.timeout) == (
        "agent_observation",
        "http://agent-observation:8000",
        600,
    )
    assert (kitchen.name, kitchen.base_url) == ("agent_kitchen", "")


def test_a_peer_s_variable_is_its_name_in_capitals() -> None:
    assert peer_url_variable("data-science") == "AGENT_DATA_SCIENCE_URL"
