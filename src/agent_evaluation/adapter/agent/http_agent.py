import json
import logging
import time
from typing import Any

import httpx

from agent_evaluation.adapter.agent.reply_collector import ReplyCollector
from agent_evaluation.adapter.agent.sse_stream import sse_events
from agent_evaluation.domain.exception import AgentUnavailable
from agent_evaluation.domain.reply import AgentReply

logger: logging.Logger = logging.getLogger(__name__)


class HttpAgent:
    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        endpoint: str,
        models_endpoint: str | None,
        model_name: str,
        timeout_seconds: float,
        headers: dict[str, str],
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._endpoint = endpoint
        self._models_endpoint = models_endpoint
        self._model_name = model_name
        self._timeout = httpx.Timeout(timeout_seconds, connect=10.0)
        self._headers = headers

    @property
    def url(self) -> str:
        return f"{self._base_url}{self._endpoint}"

    async def preflight(self) -> None:
        if not self._models_endpoint:
            return
        url = f"{self._base_url}{self._models_endpoint}"
        try:
            response = await self._client.get(url, headers=self._headers, timeout=30.0)
        except httpx.HTTPError as error:
            raise AgentUnavailable(f"the agent is not reachable at {url}: {error!r}") from error
        if response.status_code != 200:
            raise AgentUnavailable(f"GET {url} answered HTTP {response.status_code}")
        served = [str(model.get("name")) for model in response.json().get("models", [])]
        if self._model_name not in served:
            raise AgentUnavailable(
                f"the agent does not serve the model {self._model_name!r}; "
                f"pick one of: {', '.join(served) or 'none'}"
            )
        logger.info(f"Agent reachable at {self._base_url}, model {self._model_name} served")

    async def send(self, message: str, conversation_id: str, auto_approve: bool) -> AgentReply:
        payload: dict[str, Any] = {
            "message": message,
            "model_name": self._model_name,
            "request_id": conversation_id,
            "auto_approve": auto_approve,
        }
        logger.debug(f"POST {self.url} {json.dumps(payload, ensure_ascii=False)}")
        collector = ReplyCollector()
        started = time.monotonic()
        try:
            async with self._client.stream(
                "POST", self.url, json=payload, headers=self._headers, timeout=self._timeout
            ) as response:
                if response.status_code != 200:
                    body = (await response.aread()).decode(errors="replace")[:500]
                    raise AgentUnavailable(f"HTTP {response.status_code} from {self.url}: {body}")
                async for event in sse_events(response.aiter_lines()):
                    if event.name != "token":
                        logger.debug(f"event {event.name}: {_short(event.data)}")
                    collector.add(event)
        except httpx.HTTPError as error:
            raise AgentUnavailable(f"{type(error).__name__} calling {self.url}: {error}") from error
        logger.debug(f"stream closed after {collector.tokens} token events")
        return collector.reply(time.monotonic() - started)


def _short(data: dict[str, Any]) -> str:
    text = json.dumps(data, ensure_ascii=False)
    return text if len(text) <= 2000 else f"{text[:2000]}... ({len(text)} chars)"
