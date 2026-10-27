from agent_runtime.domain.conversation.conversation import Conversation
from agent_runtime.domain.turn.turn import Turn
from agent_runtime.domain.workflow.step import Step


class FinishStep:
    step = Step.FINISH

    async def run(self, conversation: Conversation, turn: Turn) -> None:
        if turn.answer is None:
            turn.finish(turn.conclude())
        if turn.leaves_plan_unfinished:
            conversation.pause(turn)
        conversation.close(turn)
