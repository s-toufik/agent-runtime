from agent_runtime.application.port.inbound.list_models_port import ListModelsPort
from agent_runtime.domain.a2a.turn_options import TurnOptions


class DescribeA2aOptions:
    def __init__(self, models: ListModelsPort, default_model: str = "") -> None:
        self._models = models
        self._default_model = default_model

    async def handle(self) -> TurnOptions:
        listing = await self._models.handle()
        names: tuple[str, ...] = tuple(model.name for model in listing.models)
        default: str = self._default_model or (names[0] if names else "")
        return TurnOptions(names, default)
