import math
from collections.abc import Sequence


def mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def percentile(values: Sequence[float], rank: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(rank / 100 * len(ordered)) - 1)
    return ordered[index]
