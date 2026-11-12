import asyncio
import socket
from typing import Literal

import pytest
from pycraftcore.application_configuration.enum import ConnectorType
from pycraftcore.application_configuration.model.connector import McpConnector
from pycraftcore.authentication.model.basic_auth import BasicAuth
from pycraftcore.authentication.model.no_auth import NoAuth
from pycraftcore.authentication.model.token_auth import TokenAuth

from agent_runtime.adapter.outbound.tool.mcp.streamable_http_session_factory import (
    StreamableHttpSessionFactory,
)
from agent_runtime.domain.exception.tool_unavailable_exception import ToolUnavailableException


def make_connector(
    auth=None, transport: Literal["sse", "streamable_http"] = "streamable_http"
) -> McpConnector:
    return McpConnector(
        name="toolbox",
        type=ConnectorType.mcp,
        auth=auth or NoAuth(),
        base_url="http://localhost:8001/mcp",
        timeout=5,
        transport=transport,
    )


class _NullLogger:
    def info(self, message: str) -> None: ...
    def warning(self, message: str) -> None: ...
    def error(self, message: str) -> None: ...
    def critical(self, message: str) -> None: ...
    def debug(self, message: str) -> None: ...
    def exception(self, message: str) -> None: ...


def fast_factory(
    connector: McpConnector | None = None,
    logger=None,
    max_attempts: int = 3,
    initial_delay: float = 0.001,
    max_delay: float = 0.001,
) -> StreamableHttpSessionFactory:
    return StreamableHttpSessionFactory(
        connector=connector or make_connector(),
        logger=logger or _NullLogger(),
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        max_delay=max_delay,
    )


def test_headers_for_token_auth() -> None:
    factory = fast_factory(
        connector=make_connector(auth=TokenAuth(key_name="Authorization", key_value="secret"))
    )

    assert factory._headers() == {"Authorization": "secret"}


def test_headers_for_basic_auth() -> None:
    factory = fast_factory(connector=make_connector(auth=BasicAuth(username="u", password="p")))

    headers = factory._headers()

    assert headers["Authorization"].startswith("Basic ")


def test_headers_for_no_auth_are_empty() -> None:
    factory = fast_factory(connector=make_connector(auth=NoAuth()))

    assert factory._headers() == {}


def _unreachable_connector() -> McpConnector:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return McpConnector(
        name="toolbox",
        type=ConnectorType.mcp,
        auth=NoAuth(),
        base_url=f"http://127.0.0.1:{port}/mcp",
        timeout=5,
        transport="streamable_http",
    )


async def test_an_unreachable_server_is_a_clean_failure_not_a_cancelled_task() -> None:
    factory = fast_factory(connector=_unreachable_connector(), max_attempts=2)

    with pytest.raises(ToolUnavailableException):
        async with factory.session():
            pass

    current = asyncio.current_task()
    assert current is not None and current.cancelling() == 0


async def test_a_cancel_from_outside_still_cancels_the_connection() -> None:
    factory = fast_factory(connector=_unreachable_connector(), max_attempts=50)

    async def connect() -> None:
        async with factory.session():
            pass

    task = asyncio.create_task(connect())
    await asyncio.sleep(0.05)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
