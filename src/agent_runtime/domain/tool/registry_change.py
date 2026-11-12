from dataclasses import dataclass, field


@dataclass(frozen=True)
class RegistryChange:
    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = field(default=(), compare=False)

    def __bool__(self) -> bool:
        return bool(self.added or self.removed)
