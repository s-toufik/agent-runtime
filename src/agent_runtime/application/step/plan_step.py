from agent_runtime.application.agent.peer_directory import PeerDirectory
from agent_runtime.application.port.outbound.planner import Planner
from agent_runtime.application.port.outbound.tool_catalog import ToolCatalog
from agent_runtime.domain.conversation.conversation import Conversation
from agent_runtime.domain.turn.answer import Answer
from agent_runtime.domain.turn.turn import Turn
from agent_runtime.domain.workflow.step import Step


class PlanStep:
    step = Step.PLAN

    def __init__(self, planner: Planner, catalog: ToolCatalog, directory: PeerDirectory) -> None:
        self._planner = planner
        self._catalog = catalog
        self._directory = directory

    async def run(self, conversation: Conversation, turn: Turn) -> None:
        plan = await self._planner.plan(
            conversation, turn, self._catalog.tools(), self._directory.peers
        )
        if plan is None:
            turn.finish(Answer.no_plan())
            return
        conversation.submit(turn, plan)
