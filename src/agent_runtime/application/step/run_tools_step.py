import asyncio

from agent_runtime.application.port.outbound.tool_executor import ToolExecutor
from agent_runtime.application.port.outbound.turn_event_publisher import TurnEventPublisher
from agent_runtime.domain.conversation.conversation import Conversation
from agent_runtime.domain.event.progress import Progress
from agent_runtime.domain.event.turn_event import TurnEvent
from agent_runtime.domain.tool.tool_call import ToolCall
from agent_runtime.domain.tool.tool_context import ToolContext
from agent_runtime.domain.tool.tool_result import ToolResult
from agent_runtime.domain.turn.turn import Turn
from agent_runtime.domain.workflow.step import Step


class RunToolsStep:
    step = Step.RUN_TOOLS

    def __init__(self, executor: ToolExecutor, events: TurnEventPublisher | None = None) -> None:
        self._executor = executor
        self._events = events

    async def run(self, conversation: Conversation, turn: Turn) -> None:
        draft = turn.last_draft
        calls = draft.tool_calls if draft else ()
        context = ToolContext(conversation=conversation.id, model=turn.model)
        turn.observed(list(await asyncio.gather(*(self._call(call, context) for call in calls))))

    async def _call(self, call: ToolCall, context: ToolContext) -> ToolResult:
        await self._tell(Progress.tool_started(call))
        result: ToolResult = await self._executor.run(call, context)
        await self._tell(Progress.tool_finished(result))
        return result

    async def _tell(self, progress: Progress) -> None:
        if self._events is not None:
            await self._events.publish(TurnEvent.progressed(progress))
