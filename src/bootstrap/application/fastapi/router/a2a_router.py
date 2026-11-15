from collections.abc import Callable
from typing import Any

from a2a.server.request_handlers import RequestHandler
from a2a.server.routes import add_a2a_routes_to_fastapi, create_jsonrpc_routes
from a2a.types.a2a_pb2 import AgentCard
from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH
from fastapi import APIRouter, FastAPI, Request

from agent_runtime.adapter.inbound.a2a.agent_card import served_card
from agent_runtime.application.port.inbound.describe_a2a_options_port import (
    DescribeA2aOptionsPort,
)

A2A_TAG: str = "A2A: Agent Card"


def a2a_card_router(
    card: AgentCard, options: Callable[[], DescribeA2aOptionsPort], a2a_path: str
) -> APIRouter:
    router = APIRouter(tags=[A2A_TAG])

    @router.get(AGENT_CARD_WELL_KNOWN_PATH)
    async def agent_card(request: Request) -> dict[str, Any]:
        root: str = str(request.url).split("?")[0].removesuffix(AGENT_CARD_WELL_KNOWN_PATH)
        return served_card(card, root + a2a_path, await options().handle())

    return router


def mount_a2a(app: FastAPI, handler: RequestHandler, base_path: str, a2a_path: str) -> None:
    add_a2a_routes_to_fastapi(
        app,
        jsonrpc_routes=create_jsonrpc_routes(
            handler, rpc_url=f"{base_path}{a2a_path}", enable_v0_3_compat=True
        ),
    )
