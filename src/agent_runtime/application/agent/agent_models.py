from dataclasses import replace

from agent_runtime.application.port.outbound.model_registry import ModelRegistry
from agent_runtime.domain.exception.unknown_model_exception import UnknownModelException
from agent_runtime.domain.llm_model.model_listing import ModelListing
from agent_runtime.domain.turn.turn_settings import TurnSettings


class AgentModels:
    def __init__(self, registry: ModelRegistry, fixed: str | None = None) -> None:
        self._registry = registry
        self._fixed = fixed
        if fixed is not None:
            served: list[str] = [model.name for model in registry.listing().models]
            if fixed not in served:
                raise UnknownModelException(
                    f"The agent's model '{fixed}' is not served (known: {', '.join(served) or 'none'})"
                )

    def model_for(self, requested: str) -> str:
        return self._fixed or self._registry.model_for(requested)

    def turn_settings(self, model: str) -> TurnSettings:
        return self._registry.turn_settings(model)

    def listing(self) -> ModelListing:
        listing: ModelListing = self._registry.listing()
        if self._fixed is None:
            return listing
        return replace(
            listing, models=tuple(model for model in listing.models if model.name == self._fixed)
        )
