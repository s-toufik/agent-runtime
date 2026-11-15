from dataclasses import dataclass

TURN_OPTIONS_URI: str = "https://github.com/s-toufik/agent-runtime/a2a/turn-options/v1"
MODEL_KEY: str = f"{TURN_OPTIONS_URI}/model"
AUTO_APPROVE_KEY: str = f"{TURN_OPTIONS_URI}/autoApprove"


@dataclass(frozen=True, slots=True)
class TurnOptions:
    models: tuple[str, ...]
    default_model: str
