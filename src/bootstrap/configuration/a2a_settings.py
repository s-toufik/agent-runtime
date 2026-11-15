from dataclasses import dataclass

from pycraftcore.application_configuration.model.operation import A2aOperation

SERVED_BINDING: str = "JSONRPC"


@dataclass(frozen=True, slots=True)
class A2aSettings:
    url: str = ""

    @classmethod
    def of(cls, operation: A2aOperation) -> A2aSettings:
        binding: str = operation.connector.binding
        if binding != SERVED_BINDING:
            raise ValueError(
                f"A2A connector {operation.connector.name!r} asks for {binding}; "
                f"only {SERVED_BINDING} is served"
            )
        return cls(url=operation.connector.base_url.strip())
