import httpx
import pytest

from agent_runtime.adapter.outbound.llm.retry_policy import should_retry_model_call

REQUEST = httpx.Request("POST", "https://llm.example/v1/chat/completions")


def _status(code: int) -> httpx.HTTPStatusError:
    response = httpx.Response(code, request=REQUEST)
    return httpx.HTTPStatusError(f"HTTP {code}", request=REQUEST, response=response)


def test_a_model_that_stays_silent_is_not_retried() -> None:
    assert not should_retry_model_call(httpx.ReadTimeout("no answer", request=REQUEST))


@pytest.mark.parametrize(
    "exception",
    [
        _status(500),
        _status(503),
        _status(429),
        httpx.ConnectError("refused", request=REQUEST),
        httpx.ConnectTimeout("no connection", request=REQUEST),
    ],
    ids=["500", "503", "429", "connect-error", "connect-timeout"],
)
def test_server_errors_and_connection_failures_are_still_retried(exception) -> None:
    assert should_retry_model_call(exception)


def test_a_rejected_request_is_not_retried() -> None:
    assert not should_retry_model_call(_status(400))
