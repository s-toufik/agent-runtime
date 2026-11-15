from agent_runtime.application.use_case.describe_a2a_options import DescribeA2aOptions
from agent_runtime.domain.a2a.turn_options import TurnOptions
from agent_runtime.domain.llm_model.model_listing import ModelListing
from tests.support.a2a import Models


class NoModels:
    async def handle(self) -> ModelListing:
        return ModelListing(models=(), pinned_steps={})


async def test_the_listed_models_with_the_first_as_default() -> None:
    assert await DescribeA2aOptions(Models()).handle() == TurnOptions(("m",), "m")


async def test_the_configured_default_wins() -> None:
    assert await DescribeA2aOptions(Models(), "big").handle() == TurnOptions(("m",), "big")


async def test_no_model_means_no_default() -> None:
    assert await DescribeA2aOptions(NoModels()).handle() == TurnOptions((), "")
