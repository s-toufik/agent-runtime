from dataclasses import dataclass

A2A_PATH: str = "/a2a"
API2A_PATH: str = "/v1/api2a"


@dataclass(frozen=True, slots=True)
class AgentRoutes:
    a2a: str = A2A_PATH
    api2a: str = API2A_PATH

    def __post_init__(self) -> None:
        for name, path in (("a2a", self.a2a), ("api2a", self.api2a)):
            if not path.startswith("/") or path.endswith("/") or "//" in path:
                raise ValueError(f"route {name} {path!r} must start with '/' and not end with one")
        if self.a2a == self.api2a:
            raise ValueError("routes a2a and api2a must differ")
