from typing import Protocol

from agent_runtime.domain.llm_model.model_listing import ModelListing


class ListModelsPort(Protocol):
    async def handle(self) -> ModelListing: ...
