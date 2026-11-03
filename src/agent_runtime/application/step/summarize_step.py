from pycraftcore.logger.port import Logger

from agent_runtime.application.port.outbound.summarizer import Summarizer
from agent_runtime.application.port.outbound.token_counter import TokenCounter
from agent_runtime.domain.conversation.conversation import Conversation
from agent_runtime.domain.turn.turn import Turn
from agent_runtime.domain.workflow.step import Step

KEEP_LAST_MESSAGES: int = 8


class SummarizeStep:
    step = Step.SUMMARIZE

    def __init__(
        self,
        summarizer: Summarizer,
        tokens: TokenCounter,
        logger: Logger,
        keep_last: int = KEEP_LAST_MESSAGES,
    ) -> None:
        self._summarizer = summarizer
        self._tokens = tokens
        self._logger = logger
        self._keep_last = keep_last

    async def run(self, conversation: Conversation, turn: Turn) -> None:
        if len(conversation.messages) <= self._keep_last:
            return
        if self._tokens.count(conversation.messages) <= turn.settings.context_tokens // 2:
            return
        try:
            summary = await self._summarizer.summarize(
                turn, conversation.summary, conversation.older_than(self._keep_last)
            )
        except Exception as exception:
            self._logger.warning(f"Summary failed, history kept as is: {exception}")
            return
        conversation.compact(summary, self._keep_last)
