import pytest
from pycraftcore.application_configuration.enum import ServerType
from pycraftcore.application_configuration.model.server import AsgiServer

from agent_runtime.adapter.outbound.llm.enum.answer_delivery import AnswerDelivery
from bootstrap.configuration.server_parameters import ServerParameters


def server(**parameters: str) -> AsgiServer:
    return AsgiServer(
        name="agent-runtime",
        type=ServerType.asgi,
        parameters=parameters,
    )


def test_the_parameters_read_from_the_environment_are_typed() -> None:
    parameters = ServerParameters.of(server(max_concurrent_streams="12", answer_delivery="whole"))

    assert parameters == ServerParameters(12, AnswerDelivery.WHOLE)


def test_an_unknown_answer_delivery_is_refused() -> None:
    with pytest.raises(ValueError):
        ServerParameters.of(server(max_concurrent_streams="12", answer_delivery="sometimes"))


def test_a_missing_parameter_is_named() -> None:
    with pytest.raises(KeyError, match="answer_delivery"):
        ServerParameters.of(server(max_concurrent_streams="12"))


def test_the_a2a_settings_are_optional() -> None:
    plain = ServerParameters.of(server(max_concurrent_streams="1", answer_delivery="stream"))
    set_ = ServerParameters.of(
        server(
            max_concurrent_streams="1",
            answer_delivery="stream",
            a2a_model="qwen3-8b",
            a2a_url="https://agent.example/a2a",
            a2a_task_ttl="3600",
        )
    )

    assert (plain.a2a_model, plain.a2a_url, plain.a2a_task_ttl) == ("", "", 604800)
    assert (set_.a2a_model, set_.a2a_url, set_.a2a_task_ttl) == (
        "qwen3-8b",
        "https://agent.example/a2a",
        3600,
    )
