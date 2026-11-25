from agent_runtime.domain.agent.peer_agent import PeerAgent

ROSTER_LEAD: str = "Agents you can hand tasks to (each one sees only the task you write):"


def agent_roster(peers: tuple[PeerAgent, ...]) -> str:
    if not peers:
        return ""
    lines: list[str] = [ROSTER_LEAD, *(f"- {peer.render()}" for peer in peers)]
    return "\n" + "\n".join(lines) + "\n"
