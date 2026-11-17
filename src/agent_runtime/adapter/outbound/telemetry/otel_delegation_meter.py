from opentelemetry import metrics

ACTIVE_DELEGATIONS: str = "agent.delegations.active"


class OtelDelegationMeter:
    """`agent.delegations.active{peer}`: 1 while this agent waits on a task it gave `peer`.

    Prometheus receives it as `agent_delegations_active`, with this agent's `job`.
    """

    def __init__(self, meter: metrics.Meter | None = None) -> None:
        source = meter or metrics.get_meter("agent-runtime.delegation")
        self._active = source.create_up_down_counter(
            ACTIVE_DELEGATIONS,
            unit="{task}",
            description="Tasks handed to another agent and not answered yet",
        )

    def started(self, agent: str) -> None:
        self._active.add(1, {"peer": agent})

    def ended(self, agent: str) -> None:
        self._active.add(-1, {"peer": agent})
