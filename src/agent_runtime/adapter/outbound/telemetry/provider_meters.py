from typing import Any

from opentelemetry import metrics


class ProviderMeters(metrics.MeterProvider):
    """Gives OpenTelemetry's global meter provider the meters of our telemetry provider.

    pycraftcore registers its tracer provider globally but not its meters, so instrumentation
    that records into the global provider (the FastAPI requests in flight, the delegations)
    would otherwise record into nothing.
    """

    def __init__(self, provider: Any) -> None:
        self._provider = provider

    def get_meter(
        self,
        name: str,
        version: str | None = None,
        schema_url: str | None = None,
        attributes: Any = None,
    ) -> metrics.Meter:
        return self._provider.meter(name)


def register_meters(provider: Any) -> None:
    metrics.set_meter_provider(ProviderMeters(provider))
