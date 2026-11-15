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

from agent_runtime.adapter.inbound.a2a.turn_options_extension import turn_options_extension
from agent_runtime.domain.a2a.turn_options import TurnOptions
from agent_runtime.domain.agent.agent import Agent

INPUT_MODES: tuple[str, ...] = ("text/plain",)
OUTPUT_MODES: tuple[str, ...] = ("text/plain", "text/markdown")


def agent_card(agent: Agent, version: str, url: str = "") -> AgentCard:
    return AgentCard(
        name=agent.name,
        description=agent.description,
        version=version,
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
            for skill in agent.skills
        ],
    )


def served_card(card: AgentCard, endpoint: str, options: TurnOptions) -> dict[str, Any]:
    served = AgentCard()
    served.CopyFrom(card)
    if not served.supported_interfaces[0].url:
        served.supported_interfaces[0].url = endpoint
    served.capabilities.extensions.append(turn_options_extension(options))
    return agent_card_to_dict(served)
