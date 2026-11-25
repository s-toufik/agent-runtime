from pycraftcore.application_configuration.model import ApiOperation

from agent_runtime.adapter.outbound.llm.model_catalog import AgentRole
from agent_runtime.adapter.outbound.llm.retry_policy import should_retry_model_call
from bootstrap.di.agent_di import AgentDI
from tests.bootstrap.di.conftest import make_settings


async def test_close_is_a_no_op_when_no_client_was_built(di) -> None:
    await di._models.close()


def test_model_calls_use_the_retry_rule_that_skips_silent_models(di) -> None:
    connector = di._models.connectors["homelab"]

    retry = di._models.transport_factory(connector)._settings.retry

    assert retry.should_retry is should_retry_model_call


async def test_each_model_provider_has_its_own_client_and_circuit_breaker(di) -> None:
    models = di._models

    breakers = {
        name: models.transport_factory(connector)._settings.circuit_breaker.name
        for name, connector in models.connectors.items()
    }

    assert set(models.http_clients) == {"homelab", "nvidia_nim"}
    assert breakers == {"homelab": "llm-homelab", "nvidia_nim": "llm-nvidia_nim"}
    await models.close()


def test_a_provider_without_a_url_leaves_its_models_out(monkeypatch) -> None:
    monkeypatch.setenv("NVIDIA_LLM_BASE_URL", "")
    models = AgentDI(make_settings())._models

    providers = {connector.name for connector, _ in models.catalog.models.values()}

    assert providers == {"homelab"}
    assert "qwen3-8b" in models.catalog.models
    assert "openai/gpt-oss-20b" not in models.catalog.models
    assert set(models.connectors) == {"homelab"}


def test_each_model_is_called_on_its_own_provider(di) -> None:
    models = di._models.catalog.models

    assert models["qwen3-8b"][0].base_url == "http://llm:8080/v1"
    assert all(
        connector.base_url == "https://integrate.api.nvidia.com/v1"
        for connector, _ in models.values()
        if connector.name == "nvidia_nim"
    )


def test_a_role_pinned_to_a_model_calls_that_model_s_provider(di) -> None:
    models = di._models
    nvidia_model = next(
        name
        for name, (connector, _) in models.catalog.models.items()
        if connector.name == "nvidia_nim"
    )
    di._configuration.operation.by_name["agent_guard"].parameters["model"] = nvidia_model

    connector, parameters = models.frozen_roles(models.catalog.models)[AgentRole.GUARD]

    assert parameters.model_name == nvidia_model
    assert connector.name == "nvidia_nim"


def test_every_model_of_llm_yml_is_selectable_by_its_server_name(di) -> None:
    operations = di._configuration.operation.by_name
    roles = {role.value for role in AgentRole}
    expected = {
        str(operation.parameters.get("model") or name)
        for name, operation in operations.items()
        if name not in roles and isinstance(operation, ApiOperation)
    }

    assert set(di._models.catalog.models) == expected


def test_only_the_roles_naming_a_model_in_agent_yml_are_frozen(di) -> None:
    operations = di._configuration.operation.by_name

    for role in AgentRole:
        configured = operations[role.value].parameters.get("model")
        frozen = di._models.catalog.roles.get(role)
        assert (frozen[1].model_name if frozen else None) == configured, role
