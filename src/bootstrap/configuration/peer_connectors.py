from collections.abc import Iterable, Mapping
from dataclasses import replace

from pycraftcore.application_configuration.model import A2aConnector

PEER_TEMPLATE: str = "agent_peer"


def peer_url_variable(peer: str) -> str:
    return f"AGENT_{peer.upper().replace('-', '_')}_URL"


def peer_connectors(
    template: A2aConnector, peers: Iterable[str], environment: Mapping[str, str]
) -> dict[str, A2aConnector]:
    return {
        peer: replace(
            template,
            name=f"agent_{peer}",
            base_url=environment.get(peer_url_variable(peer), "").strip(),
        )
        for peer in peers
    }
