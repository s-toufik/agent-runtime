from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class Route(StrEnum):
    DIRECT = "direct"
    CLARIFY = "clarify"
    PLAN = "plan"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class TurnShape:
    direct: bool = True
    clarify: bool = True
    plan: bool = True
    review: bool = True
    screen: bool = False

    def __post_init__(self) -> None:
        if not (self.direct or self.plan):
            raise ValueError("an agent needs the direct or the plan route to answer")

    @classmethod
    def of(cls, routes: Iterable[Route | str], screen: bool = False) -> TurnShape:
        allowed: set[Route] = {Route(route) for route in routes}
        return cls(
            direct=Route.DIRECT in allowed,
            clarify=Route.CLARIFY in allowed,
            plan=Route.PLAN in allowed,
            review=Route.REVIEW in allowed,
            screen=screen,
        )

    @property
    def routes(self) -> tuple[Route, ...]:
        return tuple(route for route in Route if getattr(self, route.value))
