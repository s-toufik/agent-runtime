from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fnmatch import fnmatchcase

from agent_evaluation.domain.exception import UnknownCapability


@dataclass(frozen=True, slots=True)
class Capability:
    name: str
    available: bool
    tools: tuple[str, ...] = ()

    def provides(self, tool: str) -> bool:
        return any(fnmatchcase(tool.lower(), pattern.lower()) for pattern in self.tools)


class Capabilities:
    def __init__(self, capabilities: Iterable[Capability]) -> None:
        self._by_name: Mapping[str, Capability] = {item.name: item for item in capabilities}

    def __getitem__(self, name: str) -> Capability:
        try:
            return self._by_name[name]
        except KeyError:
            raise UnknownCapability(name) from None

    def unknown(self, names: Iterable[str]) -> tuple[str, ...]:
        return tuple(name for name in names if name not in self._by_name)

    def unavailable(self, names: Iterable[str]) -> tuple[str, ...]:
        return tuple(name for name in names if not self[name].available)

    def available(self, names: Iterable[str]) -> tuple[str, ...]:
        return tuple(name for name in names if self[name].available)

    def provided_by(self, tool: str, names: Iterable[str]) -> bool:
        return any(self[name].provides(tool) for name in names)
