from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RefreshPolicy:
    interval: float = 60.0
    retry_delay: float = 5.0
    max_retry_delay: float = 60.0

    def delay_after(self, failures: int) -> float:
        if failures <= 0:
            return self.interval
        return min(self.retry_delay * 2 ** (failures - 1), self.max_retry_delay)
