from agent_runtime.application.port.inbound.list_models_port import ListModelsPort
from agent_runtime.domain.a2a.turn_options import TurnOptions


class DescribeA2aOptions:
    def __init__(self, models: ListModelsPort) -> None:
        self._models = models

    async def handle(self) -> TurnOptions:
        listing = await self._models.handle()
        names: tuple[str, ...] = tuple(model.name for model in listing.models)
        return TurnOptions(names, names[0] if names else "")
