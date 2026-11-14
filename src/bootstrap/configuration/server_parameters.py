from dataclasses import dataclass

from pycraftcore.application_configuration.model.server import AsgiServer

from agent_runtime.adapter.outbound.llm.enum.answer_delivery import AnswerDelivery


@dataclass(frozen=True, slots=True)
class ServerParameters:
    max_concurrent_streams: int
    answer_delivery: AnswerDelivery
    a2a_model: str = ""
    a2a_url: str = ""
    a2a_task_ttl: int = 604800

    @classmethod
    def of(cls, server: AsgiServer) -> ServerParameters:
        return cls(
            max_concurrent_streams=int(server.parameters["max_concurrent_streams"]),
            answer_delivery=AnswerDelivery(server.parameters["answer_delivery"]),
            a2a_model=str(server.parameters.get("a2a_model") or ""),
            a2a_url=str(server.parameters.get("a2a_url") or ""),
            a2a_task_ttl=int(server.parameters.get("a2a_task_ttl") or 604800),
        )
