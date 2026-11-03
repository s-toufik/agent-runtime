from dataclasses import dataclass

from pycraftcore.application_configuration.model.server import AsgiServer

from agent_runtime.adapter.outbound.llm.enum.answer_delivery import AnswerDelivery


@dataclass(frozen=True, slots=True)
class ServerParameters:
    max_concurrent_streams: int
    answer_delivery: AnswerDelivery

    @classmethod
    def of(cls, server: AsgiServer) -> ServerParameters:
        return cls(
            max_concurrent_streams=int(server.parameters["max_concurrent_streams"]),
            answer_delivery=AnswerDelivery(server.parameters["answer_delivery"]),
        )
