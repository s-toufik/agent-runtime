from typing import Literal

from pycraftcore.logger.port import Logger

from agent_runtime.application.port.outbound.guard import Guard
from agent_runtime.domain.conversation.conversation import Conversation
from agent_runtime.domain.turn.guard_rules import hard_block_reason
from agent_runtime.domain.turn.plan import Plan
from agent_runtime.domain.turn.screening import Screening
from agent_runtime.domain.turn.turn import Turn
from agent_runtime.domain.workflow.step import Step


class ScreenStep:
    step: Literal[Step.SCREEN] = Step.SCREEN

    def __init__(self, guard: Guard, logger: Logger) -> None:
        self._guard = guard
        self._logger = logger

    async def run(self, conversation: Conversation, turn: Turn) -> None:
        plan: Plan | None = turn.plan or conversation.pending_plan
        if plan is None:
            return
        self._logger.debug("Calling the guard rules")
        reason: str | None = hard_block_reason(plan)
        if reason is not None:
            turn.screened(Screening.block(reason))
            conversation.retract()
            turn.refuse(reason)
            self._logger.debug(f"Blocked by the guard rules: {reason}")
            return
        screening: Screening | None = await self._guard.screen(conversation, turn, plan)
        if screening is None:
            self._logger.warning("The guard could not be read; allowing the plan")
            return
        turn.screened(screening)
        if screening.blocks:
            conversation.retract()
            turn.refuse(screening.reason)
            self._logger.debug(f"Blocked by the guard model: {screening.reason}")
