import re
from dataclasses import dataclass

ALL: str = "all"
NONE: str = "none"
_NAME = re.compile(r"^[a-z][a-z0-9_-]*$")


@dataclass(frozen=True, slots=True)
class ToolScope:
    name: str = ALL

    def __post_init__(self) -> None:
        if not _NAME.match(self.name):
            raise ValueError(
                f"tool scope {self.name!r} must be lower case letters, digits, '-' or '_'"
            )

    @property
    def uses_toolbox(self) -> bool:
        return self.name != NONE

    @property
    def is_all(self) -> bool:
        return self.name == ALL
