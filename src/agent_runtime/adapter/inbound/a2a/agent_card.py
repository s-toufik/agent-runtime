from typing import Any

from a2a.server.request_handlers.response_helpers import agent_card_to_dict
from a2a.types.a2a_pb2 import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
)
from a2a.types.a2a_pb2 import (
    AgentSkill as SdkAgentSkill,
)
from a2a.utils.constants import PROTOCOL_VERSION_CURRENT, TransportProtocol

from agent_runtime.domain.a2a.agent_profile import AgentProfile

INPUT_MODES: tuple[str, ...] = ("text/plain",)
OUTPUT_MODES: tuple[str, ...] = ("text/plain", "text/markdown")


def agent_card(profile: AgentProfile, url: str = "") -> AgentCard:
    return AgentCard(
        name=profile.name,
        description=profile.description,
        version=profile.version,
        supported_interfaces=[
            AgentInterface(
                url=url,
                protocol_binding=TransportProtocol.JSONRPC.value,
                protocol_version=PROTOCOL_VERSION_CURRENT,
            )
        ],
        capabilities=AgentCapabilities(streaming=True, push_notifications=False),
        default_input_modes=list(INPUT_MODES),
        default_output_modes=list(OUTPUT_MODES),
        skills=[
            SdkAgentSkill(
                id=skill.id,
                name=skill.name,
                description=skill.description,
                tags=list(skill.tags),
                examples=list(skill.examples),
            )
            for skill in profile.skills
        ],
    )


def served_card(card: AgentCard, endpoint: str) -> dict[str, Any]:
    if card.supported_interfaces and card.supported_interfaces[0].url:
        return agent_card_to_dict(card)
    served = AgentCard()
    served.CopyFrom(card)
    served.supported_interfaces[0].url = endpoint
    return agent_card_to_dict(served)
