from agent_runtime.domain.conversation.conversation import Conversation
from agent_runtime.domain.turn.answer import Answer
from agent_runtime.domain.turn.turn import Turn
from agent_runtime.domain.workflow.step import Step


class ClarifyStep:
    step = Step.CLARIFY

    async def run(self, conversation: Conversation, turn: Turn) -> None:
        understanding = turn.understanding
        question = understanding.clarification_question if understanding else None
        turn.finish(Answer.clarification(question or ""))
