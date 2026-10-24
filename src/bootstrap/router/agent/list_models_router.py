from pycraftcore.web.schema import HttpRoute

from agent_runtime.adapter.inbound.web.controller.list_models_controller import (
    ListModelsController,
)
from agent_runtime.adapter.inbound.web.schema.model_list_schema import ModelListSchema


class ListModelsRouter:
    PREFIX: str = "/v1"
    ENDPOINT: str = "/models"

    def __init__(self, controller: ListModelsController) -> None:
        self._controller = controller

    @property
    def routes(self) -> list[HttpRoute]:
        return [
            HttpRoute(
                method="GET",
                path=self.PREFIX + self.ENDPOINT,
                handler=self._controller.execute,
                response=ModelListSchema,
            )
        ]
