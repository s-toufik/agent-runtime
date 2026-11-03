from typing import Annotated

import msgspec

from agent_runtime.domain.llm_model.model_listing import ModelListing


class ModelSchema(msgspec.Struct):
    name: Annotated[str, msgspec.Meta(description="The value to send as model_name.")]
    context_tokens: int
    max_output_tokens: int
    thinking: Annotated[
        bool, msgspec.Meta(description="Whether the model reasons before answering.")
    ]


class ModelListSchema(msgspec.Struct):
    models: list[ModelSchema]
    pinned_steps: Annotated[
        dict[str, str],
        msgspec.Meta(description="Steps that always use one model, whatever model_name asks for."),
    ] = msgspec.field(default_factory=dict)

    @classmethod
    def from_domain(cls, listing: ModelListing) -> ModelListSchema:
        return cls(
            models=[
                ModelSchema(
                    name=model.name,
                    context_tokens=model.context_tokens,
                    max_output_tokens=model.max_output_tokens,
                    thinking=model.thinking,
                )
                for model in listing.models
            ],
            pinned_steps={step.value: model for step, model in listing.pinned_steps.items()},
        )
