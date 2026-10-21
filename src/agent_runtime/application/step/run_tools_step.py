import asyncio

from agent_runtime.application.port.outbound.tool_executor import ToolExecutor
from agent_runtime.domain.conversation.conversation import Conversation
from agent_runtime.domain.turn.turn import Turn
from agent_runtime.domain.workflow.step import Step


class RunToolsStep:
    step = Step.RUN_TOOLS

    def __init__(self, executor: ToolExecutor) -> None:
        self._executor = executor

    async def run(self, conversation: Conversation, turn: Turn) -> None:
        draft = turn.last_draft
        calls = draft.tool_calls if draft else ()
        turn.observed(list(await asyncio.gather(*(self._executor.run(call) for call in calls))))
