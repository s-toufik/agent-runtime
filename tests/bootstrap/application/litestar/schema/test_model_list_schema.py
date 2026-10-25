import msgspec

from bootstrap.application.litestar.schema.model_list_schema import ModelListSchema
from tests.agent_runtime.application.fakes import LISTING


def test_from_domain_maps_models_and_pinned_steps() -> None:
    schema = ModelListSchema.from_domain(LISTING)

    assert msgspec.to_builtins(schema) == {
        "models": [
            {"name": "m", "context_tokens": 8_000, "max_output_tokens": 1_000, "thinking": False}
        ],
        "pinned_steps": {"understand": "small"},
    }
