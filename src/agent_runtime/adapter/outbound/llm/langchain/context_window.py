import json
import re
from collections.abc import Sequence
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    SystemMessage,
    ToolMessage,
    trim_messages,
)

from agent_runtime.adapter.outbound.llm.langchain.messages import from_history
from agent_runtime.adapter.outbound.llm.langchain.token_counter import count_texts, count_tokens
from agent_runtime.domain.conversation.conversation import Conversation

_SUMMARY_SECTION = "\n\nSummary of the earlier conversation:\n{summary}"
_ACTIONS_SECTION = (
    "\n\nTools you ran earlier in this conversation, oldest first "
    "(reuse their results instead of running them again):\n{actions}"
)
_SHORTENED = (
    "\n[… shortened to fit the model's context: about {left_out} of {total} tokens left out. "
    "If you need the rest, call the tool again asking for less: a filter, a limit, fewer fields.]"
)
_WORD = re.compile(r"\S+")

SAFETY_MARGIN: float = 0.85
RESULT_SHARE: float = 0.25
SHORTEST_RESULT: int = 60


def count_message_tokens(messages: Sequence[BaseMessage]) -> int:
    return count_texts(_counted(m) for m in messages)


def count_tool_tokens(tools: Sequence[Any]) -> int:
    return sum(count_tokens(json.dumps(tool, default=str)) for tool in tools)


def input_budget(context_tokens: int, output_tokens: int, tools: Sequence[Any] = ()) -> int:
    answer_room: int = min(output_tokens, context_tokens // 2)
    room: int = context_tokens - answer_room - count_tool_tokens(tools)
    return max(int(room * SAFETY_MARGIN), 0)


class ContextWindow:
    def build(
        self,
        system: str,
        conversation: Conversation,
        budget: int,
        tail: Sequence[BaseMessage] = (),
    ) -> list[BaseMessage]:
        if conversation.summary:
            system += _SUMMARY_SECTION.format(summary=conversation.summary)
        if conversation.actions:
            actions = "\n".join(f"- {action.render()}" for action in conversation.actions)
            system += _ACTIONS_SECTION.format(actions=actions)
        head = SystemMessage(content=system)
        fitted: list[BaseMessage] = fit_tail(tail, budget - count_message_tokens([head]))
        reserved = count_message_tokens([head, *fitted])
        return [head, *self.history(conversation, budget - reserved), *fitted]

    @staticmethod
    def history(conversation: Conversation, budget: int) -> list[BaseMessage]:
        return trim_messages(
            from_history(conversation.messages),
            token_counter=count_message_tokens,
            max_tokens=max(budget, 0),
            strategy="last",
            start_on="human",
        )


def fit_tail(tail: Sequence[BaseMessage], room: int) -> list[BaseMessage]:
    fitted: list[BaseMessage] = list(tail)
    if count_message_tokens(fitted) <= room:
        return fitted
    results: list[int] = [i for i, message in enumerate(fitted) if isinstance(message, ToolMessage)]
    if not results:
        return fitted

    share: int = max(int(room * RESULT_SHARE), SHORTEST_RESULT)
    for i in results:
        fitted[i] = shorten(fitted[i], share)

    for i in results[:-1]:
        if count_message_tokens(fitted) <= room:
            return fitted
        fitted[i] = shorten(fitted[i], SHORTEST_RESULT)

    latest: int = results[-1]
    overflow: int = count_message_tokens(fitted) - room
    if overflow > 0:
        size: int = count_tokens(_text(fitted[latest]))
        fitted[latest] = shorten(fitted[latest], max(size - overflow, SHORTEST_RESULT))
    return fitted


def shorten(message: BaseMessage, tokens: int) -> BaseMessage:
    content: str = _text(message)
    total: int = count_tokens(content)
    if total <= tokens:
        return message
    note_room: int = count_tokens(_SHORTENED.format(left_out=total, total=total))
    end: int = 0
    used: int = 0
    for word in _WORD.finditer(content):
        cost: int = count_tokens(word.group())
        if used + cost > max(tokens - note_room, 0):
            break
        used += cost
        end = word.end()
    kept: str = content[:end] + _SHORTENED.format(left_out=total - used, total=total)
    return message.model_copy(update={"content": kept})


def _counted(message: BaseMessage) -> str:
    if isinstance(message, AIMessage) and message.tool_calls:
        return _text(message) + json.dumps(message.tool_calls, default=str)
    return _text(message)


def _text(message: BaseMessage) -> str:
    return message.content if isinstance(message.content, str) else str(message.content)
