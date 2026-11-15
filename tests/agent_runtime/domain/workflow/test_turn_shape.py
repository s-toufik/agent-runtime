import pytest

from agent_runtime.domain.workflow.turn_shape import Route, TurnShape


def test_a_shape_is_built_from_the_routes_it_allows() -> None:
    shape = TurnShape.of(["clarify", "plan", "review"])

    assert shape == TurnShape(direct=False, clarify=True, plan=True, review=True)
    assert shape.routes == (Route.CLARIFY, Route.PLAN, Route.REVIEW)


def test_every_route_is_allowed_by_default() -> None:
    assert TurnShape().routes == tuple(Route)


def test_an_unknown_route_is_refused() -> None:
    with pytest.raises(ValueError, match="'shortcut' is not a valid Route"):
        TurnShape.of(["direct", "shortcut"])


def test_a_shape_without_direct_nor_plan_cannot_answer() -> None:
    with pytest.raises(ValueError, match="direct or the plan route"):
        TurnShape.of(["clarify", "review"])
