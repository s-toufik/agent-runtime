from typing import Protocol


class DelegationMeter(Protocol):
    """Counts the tasks this agent has handed to another agent and is still waiting on."""

    def started(self, agent: str) -> None: ...

    def ended(self, agent: str) -> None: ...
