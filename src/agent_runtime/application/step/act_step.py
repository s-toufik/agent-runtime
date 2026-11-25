from agent_runtime.application.agent.peer_directory import PeerDirectory
from agent_runtime.application.port.outbound.actor import Actor
from agent_runtime.application.port.outbound.tool_catalog import ToolCatalog
from agent_runtime.domain.conversation.conversation import Conversation
from agent_runtime.domain.turn.turn import Turn
from agent_runtime.domain.workflow.step import Step


class ActStep:
    step = Step.ACT

    def __init__(self, actor: Actor, catalog: ToolCatalog, directory: PeerDirectory) -> None:
        self._actor = actor
        self._catalog = catalog
        self._directory = directory

    async def run(self, conversation: Conversation, turn: Turn) -> None:
        draft = await self._actor.act(
            conversation, turn, self._catalog.tools(), self._directory.peers
        )
        turn.drafted(draft)
