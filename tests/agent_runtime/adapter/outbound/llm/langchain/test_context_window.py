from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent_runtime.adapter.outbound.llm.langchain.context_window import (
    RESULT_SHARE,
    SAFETY_MARGIN,
    SHORTEST_RESULT,
    ContextWindow,
    count_message_tokens,
    count_tool_tokens,
    fit_tail,
    input_budget,
    shorten,
)
from agent_runtime.domain.conversation.conversation import Conversation
from agent_runtime.domain.conversation.message import Message, Speaker


def _logs(lines: int) -> str:
    return "\n".join(
        f'{{"level": "info", "msg": "request {i} served in 12 ms"}}' for i in range(lines)
    )


def _work(*results: str) -> list:
    messages: list = [HumanMessage(content="find the errors")]
    for i, content in enumerate(results):
        messages.append(
            AIMessage(content="", tool_calls=[{"id": f"c{i}", "name": "loki", "args": {"q": "x"}}])
        )
        messages.append(ToolMessage(content=content, tool_call_id=f"c{i}"))
    return messages


def test_the_input_keeps_room_for_the_answer_the_tools_and_a_margin() -> None:
    tools = [{"name": "loki", "description": "Query logs.", "parameters": {"type": "object"}}]

    budget = input_budget(32_768, 8_192, tools)

    assert budget == int((32_768 - 8_192 - count_tool_tokens(tools)) * SAFETY_MARGIN)


def test_the_answer_never_takes_more_than_half_the_context() -> None:
    assert input_budget(8_000, 8_192) == int(4_000 * SAFETY_MARGIN)


def test_a_tail_that_fits_is_sent_as_it_is() -> None:
    tail = _work("three lines of logs")

    assert fit_tail(tail, 10_000) == tail


def test_an_oversized_tool_result_is_shortened_and_says_so() -> None:
    tail = _work(_logs(2_000))

    fitted = fit_tail(tail, 2_000)

    assert count_message_tokens(fitted) <= 2_000
    shortened = fitted[-1]
    assert isinstance(shortened, ToolMessage)
    assert shortened.tool_call_id == "c0"
    assert shortened.content.startswith('{"level": "info", "msg": "request 0 served')
    assert "shortened to fit the model's context" in shortened.content
    assert "asking for less" in shortened.content


def test_each_result_is_capped_to_a_share_when_that_is_enough() -> None:
    tail = _work(_logs(400), _logs(400), _logs(400))

    fitted = fit_tail(tail, 3_000)
    sizes = [count_message_tokens([m]) for m in fitted if isinstance(m, ToolMessage)]

    assert count_message_tokens(fitted) <= 3_000
    assert max(sizes) <= int(3_000 * RESULT_SHARE) + 4


def test_older_results_shrink_first_and_the_latest_keeps_the_most() -> None:
    tail = _work(*(_logs(400) for _ in range(5)))

    fitted = fit_tail(tail, 2_000)
    sizes = [count_message_tokens([m]) for m in fitted if isinstance(m, ToolMessage)]

    assert count_message_tokens(fitted) <= 2_000
    assert sizes[0] <= SHORTEST_RESULT + 4
    assert sizes[-1] > 4 * sizes[0]
    assert [m.type for m in fitted] == [m.type for m in tail]


def test_every_tool_call_keeps_its_result() -> None:
    tail = _work(_logs(500), _logs(500))

    fitted = fit_tail(tail, 500)

    calls = [c["id"] for m in fitted if isinstance(m, AIMessage) for c in m.tool_calls]
    answered = [m.tool_call_id for m in fitted if isinstance(m, ToolMessage)]
    assert calls == answered == ["c0", "c1"]


def test_shortening_keeps_the_text_as_it_was_up_to_the_cut() -> None:
    message = ToolMessage(content="line one\n  line two\nline three " * 50, tool_call_id="c0")

    shortened = shorten(message, 80)

    assert shortened.content.startswith("line one\n  line two\nline three line one")


def test_tool_call_arguments_count_towards_the_size() -> None:
    code = "result = sum(range(10))\n" * 100
    with_code = AIMessage(
        content="", tool_calls=[{"id": "c0", "name": "python_executor", "args": {"code": code}}]
    )

    assert count_message_tokens([with_code]) > 500


def test_the_built_request_fits_its_budget_whatever_the_tool_returned() -> None:
    conversation = Conversation(
        "c1",
        messages=[
            Message(Speaker.USER if i % 2 == 0 else Speaker.ASSISTANT, f"message {i} " * 30)
            for i in range(40)
        ],
    )
    budget = input_budget(32_768, 8_192)

    built = ContextWindow().build("system prompt " * 200, conversation, budget, _work(_logs(5_000)))

    assert count_message_tokens(built) <= budget
    assert isinstance(built[-1], ToolMessage)
