from collections.abc import Iterable

from agent_runtime.domain.agent.peer_agent import PeerAgent


class PeerDirectory:
    def __init__(self) -> None:
        self._peers: dict[str, PeerAgent] = {}

    @property
    def peers(self) -> tuple[PeerAgent, ...]:
        return tuple(self._peers.values())

    def get(self, name: str) -> PeerAgent | None:
        return self._peers.get(name)

    def replace(self, peers: Iterable[PeerAgent]) -> None:
        self._peers = {peer.name: peer for peer in peers}
