from typing import cast

from agent_runtime.adapter.inbound.web.controller.list_models_controller import (
    ListModelsController,
)
from agent_runtime.adapter.inbound.web.schema.model_list_schema import ModelListSchema
from bootstrap.router.agent.list_models_router import ListModelsRouter
from tests.agent_runtime.application.fakes import LISTING
from tests.support.web import EVERY_FRAMEWORK, build_app, http_client


class FakeController:
    async def execute(self) -> ModelListSchema:
        return ModelListSchema.from_domain(LISTING)


@EVERY_FRAMEWORK
async def test_getting_the_endpoint_returns_the_controller_listing(framework) -> None:
    routes = ListModelsRouter(cast(ListModelsController, FakeController())).routes

    async with http_client(build_app(framework, routes)) as client:
        response = await client.get("/v1/models")

    assert response.status_code == 200
    assert response.json() == {
        "models": [
            {"name": "m", "context_tokens": 8000, "max_output_tokens": 1000, "thinking": False}
        ],
        "pinned_steps": {"understand": "small"},
    }
