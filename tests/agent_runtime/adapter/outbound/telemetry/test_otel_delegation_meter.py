from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from agent_runtime.adapter.outbound.telemetry.otel_delegation_meter import (
    ACTIVE_DELEGATIONS,
    OtelDelegationMeter,
)
from agent_runtime.adapter.outbound.telemetry.provider_meters import ProviderMeters


def _active(reader: InMemoryMetricReader) -> dict[str, int]:
    data = reader.get_metrics_data()
    points = [
        point
        for resource in data.resource_metrics
        for scope in resource.scope_metrics
        for metric in scope.metrics
        if metric.name == ACTIVE_DELEGATIONS
        for point in metric.data.data_points
    ]
    return {str(point.attributes["peer"]): int(point.value) for point in points}


def test_a_delegation_counts_while_the_agent_waits_and_drops_when_it_answers() -> None:
    reader = InMemoryMetricReader()
    meter = OtelDelegationMeter(MeterProvider(metric_readers=[reader]).get_meter("test"))

    meter.started("observation")
    meter.started("security")
    assert _active(reader) == {"observation": 1, "security": 1}

    meter.ended("observation")
    assert _active(reader) == {"observation": 0, "security": 1}


def test_global_meters_come_from_our_telemetry_provider() -> None:
    reader = InMemoryMetricReader()
    sdk = MeterProvider(metric_readers=[reader])

    class Provider:
        def meter(self, name: str):
            return sdk.get_meter(name)

    meter = OtelDelegationMeter(ProviderMeters(Provider()).get_meter("agent-runtime.delegation"))
    meter.started("kitchen")

    assert _active(reader) == {"kitchen": 1}
