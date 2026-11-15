import pytest

from agent_runtime.application.agent.agent_models import AgentModels
from agent_runtime.domain.exception.unknown_model_exception import UnknownModelException
from tests.agent_runtime.application.fakes import FakeModels
from tests.support.a2a import listing_of


def test_without_a_model_of_its_own_the_agent_uses_the_requested_one() -> None:
    models = AgentModels(FakeModels())

    assert models.model_for("m") == "m"
    assert [model.name for model in models.listing().models] == ["m"]


def test_an_agent_with_its_own_model_uses_it_whatever_is_requested() -> None:
    models = AgentModels(FakeModels(), "m")

    assert models.model_for("anything else") == "m"
    assert models.listing().pinned_steps == FakeModels().listing().pinned_steps


def test_an_agent_with_its_own_model_lists_only_that_one(monkeypatch) -> None:
    registry = FakeModels()
    monkeypatch.setattr(registry, "listing", lambda: listing_of("m", "big"))

    assert [model.name for model in AgentModels(registry, "big").listing().models] == ["big"]


def test_a_model_no_provider_serves_stops_the_agent_at_boot() -> None:
    with pytest.raises(UnknownModelException, match="'missing' is not served \\(known: m\\)"):
        AgentModels(FakeModels(), "missing")
