from dataclasses import dataclass
from typing import Any

from a2a.types.a2a_pb2 import AgentExtension

from agent_runtime.domain.a2a.turn_options import (
    AUTO_APPROVE_KEY,
    MODEL_KEY,
    TURN_OPTIONS_URI,
    TurnOptions,
)

__all__ = [
    "AUTO_APPROVE_KEY",
    "MODEL_KEY",
    "TURN_OPTIONS_URI",
    "requested_options",
    "turn_options_extension",
]

DESCRIPTION: str = (
    f"Message metadata the agent reads. '{MODEL_KEY}': the model of the turn, one of "
    f"params.models (default: params.defaultModel). '{AUTO_APPROVE_KEY}': true runs a plan "
    "without waiting for a 'yes' in the same task."
)


@dataclass(frozen=True, slots=True)
class RequestedOptions:
    model: str = ""
    auto_approve: bool = False


def turn_options_extension(options: TurnOptions) -> AgentExtension:
    extension = AgentExtension(uri=TURN_OPTIONS_URI, description=DESCRIPTION, required=False)
    extension.params.update({"models": list(options.models), "defaultModel": options.default_model})
    return extension


def requested_options(metadata: dict[str, Any]) -> RequestedOptions:
    model: Any = metadata.get(MODEL_KEY)
    auto_approve: Any = metadata.get(AUTO_APPROVE_KEY)
    return RequestedOptions(
        model=model.strip() if isinstance(model, str) else "",
        auto_approve=auto_approve is True,
    )
