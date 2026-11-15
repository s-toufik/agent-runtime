from typing import Protocol

from agent_runtime.domain.llm_model.model_listing import ModelListing
from agent_runtime.domain.turn.turn_settings import TurnSettings


class ModelRegistry(Protocol):
    def model_for(self, requested: str) -> str: ...

    def turn_settings(self, model: str) -> TurnSettings: ...

    def listing(self) -> ModelListing: ...
