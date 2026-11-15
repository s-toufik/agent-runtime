import pytest
from pycraftcore.application_configuration.enum import ConnectorType
from pycraftcore.application_configuration.enum.operation_type import OperationType
from pycraftcore.application_configuration.model.connector import A2aConnector
from pycraftcore.application_configuration.model.operation import A2aOperation
from pycraftcore.authentication.model.no_auth import NoAuth

from bootstrap.configuration.a2a_settings import A2aSettings


def operation(base_url: str = "", binding: str = "JSONRPC", **parameters) -> A2aOperation:
    connector = A2aConnector(
        name="a2a_self",
        type=ConnectorType.a2a,
        auth=NoAuth(),
        base_url=base_url,
        timeout=300,
        binding=binding,
    )
    return A2aOperation(
        name="a2a", type=OperationType.a2a, connector=connector, parameters=parameters
    )


def test_the_url_comes_from_the_connector() -> None:
    settings = A2aSettings.of(operation(" https://agent.example/a2a "))

    assert settings == A2aSettings("https://agent.example/a2a")


def test_no_url_means_the_address_the_card_was_read_from() -> None:
    assert A2aSettings.of(operation()) == A2aSettings("")


def test_only_json_rpc_is_served() -> None:
    with pytest.raises(ValueError, match="asks for GRPC; only JSONRPC is served"):
        A2aSettings.of(operation(binding="GRPC"))
