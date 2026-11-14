import asyncio

from agent_runtime.domain.event.turn_event import TurnEvent, TurnEventKind
from agent_runtime.domain.request.agent_request import AgentRequest
from agent_runtime.domain.turn.answer import Answer
from agent_runtime.domain.turn.outcome import Outcome
from agent_runtime.domain.turn.token_usage import TokenUsage
from agent_runtime.domain.workflow.step import Step
from tests.agent_runtime.application.fakes import LISTING


def finished(text: str, outcome: Outcome = Outcome.ANSWERED, resumable: bool = False) -> TurnEvent:
    return TurnEvent(
        TurnEventKind.FINISHED,
        answer=Answer(text, outcome, resumable),
        model="m",
        usage=TokenUsage(input_tokens=3, output_tokens=2),
    )


ANSWERED = [TurnEvent(TurnEventKind.STEP_STARTED, step=Step.UNDERSTAND), finished("42")]
PLANNED = [finished("### Plan\n1. echo", Outcome.AWAITING_APPROVAL)]


class ScriptedUseCase:
    def __init__(self, *turns: list[TurnEvent]) -> None:
        self._turns = list(turns)
        self.requests: list[AgentRequest] = []

    async def handle(self, request: AgentRequest, events) -> None:
        self.requests.append(request)
        for event in self._turns.pop(0):
            await events.publish(event)
        await events.complete()


class HangingUseCase:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.requests: list[AgentRequest] = []

    async def handle(self, request: AgentRequest, events) -> None:
        self.requests.append(request)
        self.started.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            self.cancelled.set()
            raise


class Models:
    async def handle(self):
        return LISTING
