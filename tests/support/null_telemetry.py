import logging

from opentelemetry.metrics import Meter, NoOpMeter
from pycraftcore.application_configuration.enum.run_type_environment import RunTypeEnvironment
from pycraftcore.telemetry.adapter import NullTelemetryTracer
from pycraftcore.telemetry.port import TelemetryTracer


class NullTelemetryProvider:
    """A TelemetryProvider that exports nothing and starts no OpenTelemetry SDK threads."""

    def __init__(
        self,
        service_name: str,
        environment: RunTypeEnvironment = RunTypeEnvironment.debug,
        otlp_endpoint: str | None = None,
    ) -> None:
        self.service_name = service_name
        self.environment = environment
        self.otlp_endpoint = otlp_endpoint
        self.is_shut_down = False

    def tracer(self, service_name: str) -> TelemetryTracer:
        return NullTelemetryTracer()

    def log_handler(self) -> logging.Handler:
        return logging.NullHandler()

    def meter(self, service_name: str) -> Meter:
        return NoOpMeter(service_name)

    def shutdown(self) -> None:
        self.is_shut_down = True
