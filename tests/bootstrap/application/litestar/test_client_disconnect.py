import asyncio

import httpx

from agent_runtime.adapter.inbound.web.stream.stream_agent_controller import (
    StreamAgentController,
)
from agent_runtime.adapter.outbound.event.queue_turn_event_stream import QueueTurnEventStream
from tests.bootstrap.application.litestar.support import litestar_api
from tests.support.web import running_server

BODY = {"message": "hi", "model_name": "m", "request_id": "r1"}


class HangingUseCase:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def handle(self, request, events) -> None:
        self.started.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            self.cancelled.set()
            raise


class NoModels:
    async def handle(self): ...


async def test_a_client_disconnect_cancels_the_turn_and_frees_its_slot(logger) -> None:
    use_case = HangingUseCase()
    controller = StreamAgentController(
        use_case, QueueTurnEventStream, logger, max_concurrent_streams=1, heartbeat_seconds=None
    )
    app = litestar_api(logger, lambda: controller, NoModels)

    async with running_server(app) as base_url:
        async with httpx.AsyncClient(base_url=base_url) as client:
            async with client.stream("POST", "/v1/stream", json=BODY) as response:
                assert response.status_code == 200
                await use_case.started.wait()

        await asyncio.wait_for(use_case.cancelled.wait(), timeout=5)
        await asyncio.wait_for(controller._admission.acquire(), timeout=5)
