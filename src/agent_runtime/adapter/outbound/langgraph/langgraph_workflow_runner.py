from collections.abc import AsyncIterator
from contextlib import nullcontext
from typing import Any

from pycraftcore.logger.port import Logger

from agent_runtime.adapter.outbound.langgraph.state.graph_state import GraphState
from agent_runtime.adapter.outbound.langgraph.state.turn_state_codec import TurnStateCodec
from agent_runtime.application.port.outbound.usage_meter import UsageMeter, UsageScope
from agent_runtime.domain.conversation.conversation import Conversation
from agent_runtime.domain.event.turn_event import TurnEvent
from agent_runtime.domain.turn.token_usage import TokenUsage
from agent_runtime.domain.turn.turn import Turn
from agent_runtime.domain.turn.turn_settings import TurnSettings


class LangGraphWorkflowRunner:
    def __init__(self, graph: Any, logger: Logger, usage_meter: UsageMeter | None = None) -> None:
        self._graph = graph
        self._logger = logger
        self._usage_meter = usage_meter
        self._codec = TurnStateCodec()

    @property
    def graph(self) -> Any:
        return self._graph

    async def run(self, conversation_id: str, turn: Turn) -> AsyncIterator[TurnEvent]:
        config: dict[str, Any] = self._config(conversation_id, turn)
        conversation: Conversation = await self._load(conversation_id, config)

        final: GraphState | None = None
        measure = self._usage_meter.measure() if self._usage_meter is not None else nullcontext()
        with measure as scope:
            async for mode, chunk in self._graph.astream(
                self._codec.encode(conversation, turn),
                config=config,
                stream_mode=["custom", "values"],
            ):
                if mode == "custom":
                    yield chunk
                else:
                    final = chunk
            if final is None:
                raise RuntimeError("The workflow finished without producing a state")
            usage: TokenUsage | None = self._read(scope)
        yield TurnEvent.finished(self._codec.decode_turn(final), usage=usage)

    def _read(self, scope: UsageScope | None) -> TokenUsage | None:
        if scope is None:
            return None
        try:
            return scope.usage()
        except Exception as exception:
            self._logger.warning(f"Token usage capture failed: {exception}")
            return None

    @staticmethod
    def _config(conversation_id: str, turn: Turn) -> dict[str, Any]:
        settings: TurnSettings = turn.settings
        limit: int = 10 + 2 * settings.max_steps + 3 * settings.max_retries
        return {"configurable": {"thread_id": conversation_id}, "recursion_limit": limit}

    async def _load(self, conversation_id: str, config: dict[str, Any]) -> Conversation:
        snapshot: Any = await self._graph.aget_state(config)
        if not snapshot.values:
            return Conversation(conversation_id)
        stored: Conversation | None = self._codec.stored_conversation(snapshot.values)
        if stored is None:
            self._logger.warning(
                f"Conversation {conversation_id} has an unreadable state: new start"
            )
            return Conversation(conversation_id)
        return stored
