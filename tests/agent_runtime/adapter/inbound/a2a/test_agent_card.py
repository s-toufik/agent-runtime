from agent_runtime.adapter.inbound.a2a.agent_card import agent_card, served_card
from agent_runtime.domain.a2a.agent_profile import HOMELAB_ASSISTANT, AgentProfile

PROFILE = AgentProfile("agent-runtime", "1.2.3")


def test_the_card_describes_the_profile_over_json_rpc_with_streaming() -> None:
    card = served_card(agent_card(PROFILE, "https://a.example/a2a"), "ignored")

    assert card["name"] == "agent-runtime"
    assert card["version"] == "1.2.3"
    assert card["supportedInterfaces"] == [
        {"url": "https://a.example/a2a", "protocolBinding": "JSONRPC", "protocolVersion": "1.0"}
    ]
    assert card["capabilities"] == {"streaming": True, "pushNotifications": False}
    assert [skill["id"] for skill in card["skills"]] == [HOMELAB_ASSISTANT.id]


def test_a_card_without_a_url_names_the_endpoint_it_was_read_from() -> None:
    card = agent_card(PROFILE)

    served = served_card(card, "http://agent:8000/a2a")

    assert served["supportedInterfaces"][0]["url"] == "http://agent:8000/a2a"
    assert card.supported_interfaces[0].url == ""
