from agent_runtime.adapter.inbound.a2a.agent_card import agent_card, served_card
from agent_runtime.adapter.inbound.a2a.turn_options_extension import TURN_OPTIONS_URI
from agent_runtime.domain.a2a.turn_options import TurnOptions
from tests.support.agents import AGENT, SKILL

OPTIONS = TurnOptions(models=("small", "big"), default_model="small")


def test_the_card_describes_the_profile_over_json_rpc_with_streaming() -> None:
    card = served_card(agent_card(AGENT, "1.2.3", "https://a.example/a2a"), "ignored", OPTIONS)

    assert card["name"] == "agent-runtime"
    assert card["version"] == "1.2.3"
    assert card["supportedInterfaces"] == [
        {"url": "https://a.example/a2a", "protocolBinding": "JSONRPC", "protocolVersion": "1.0"}
    ]
    assert card["capabilities"]["streaming"] is True
    assert card["capabilities"]["pushNotifications"] is False
    assert [skill["id"] for skill in card["skills"]] == [SKILL.id]


def test_a_card_without_a_url_names_the_endpoint_it_was_read_from() -> None:
    card = agent_card(AGENT, "1.2.3")

    served = served_card(card, "http://agent:8000/a2a", OPTIONS)

    assert served["supportedInterfaces"][0]["url"] == "http://agent:8000/a2a"
    assert card.supported_interfaces[0].url == ""


def test_the_card_offers_the_turn_options_as_an_optional_extension() -> None:
    card = served_card(agent_card(AGENT, "1.2.3"), "http://agent:8000/a2a", OPTIONS)

    [extension] = card["capabilities"]["extensions"]
    assert extension["uri"] == TURN_OPTIONS_URI
    assert extension.get("required", False) is False
    assert extension["params"] == {"models": ["small", "big"], "defaultModel": "small"}
    assert f"{TURN_OPTIONS_URI}/model" in extension["description"]


def test_serving_the_card_leaves_the_built_card_unchanged() -> None:
    card = agent_card(AGENT, "1.2.3")

    served_card(card, "http://agent:8000/a2a", OPTIONS)
    served_card(card, "http://agent:8000/a2a", OPTIONS)

    assert list(card.capabilities.extensions) == []
