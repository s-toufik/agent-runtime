from agent_runtime.application.use_case.list_models import ListModels
from tests.agent_runtime.application.fakes import LISTING, FakeModels


async def test_the_listing_is_the_registry_s() -> None:
    assert await ListModels(FakeModels()).handle() == LISTING
