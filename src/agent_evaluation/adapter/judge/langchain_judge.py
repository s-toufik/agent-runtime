import logging
from collections.abc import Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field, SecretStr

from agent_evaluation.adapter.judge.prompts import judge_request, judge_system_prompt
from agent_evaluation.domain.check.judge import Grade
from agent_evaluation.domain.exception import JudgeUnavailable
from agent_evaluation.domain.exchange import Exchange
from agent_runtime.adapter.outbound.llm.enum.reasoning_effort import ReasoningEffort
from agent_runtime.adapter.outbound.llm.langchain.chat_factory import LLMChat
from agent_runtime.adapter.outbound.llm.langchain.model_call import invoke_structured
from agent_runtime.adapter.outbound.llm.schema import ModelConnector, ModelParameters

logger: logging.Logger = logging.getLogger(__name__)


class GradeDto(BaseModel):
    score: float = Field(ge=0.0, le=1.0, description="How well the criterion is met, 0 to 1.")
    reason: str = Field(description="One or two sentences pointing at the evidence.")


class LangChainJudge:
    def __init__(self, model: BaseChatModel) -> None:
        self._model = model

    @classmethod
    def from_settings(
        cls,
        base_url: str,
        api_key: str,
        model_name: str,
        temperature: float,
        max_output_tokens: int,
        max_context_tokens: int,
        reasoning_effort: str | None,
    ) -> LangChainJudge:
        chat = LLMChat(
            ModelConnector(base_url=base_url, api_key=SecretStr(api_key)),
            ModelParameters(
                model_name=model_name,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                max_context_tokens=max_context_tokens,
                max_iterations=1,
                reasoning_effort=ReasoningEffort(reasoning_effort) if reasoning_effort else None,
                stream_usage=False,
            ),
        )
        return cls(chat.create_chat_client())

    async def grade(self, criterion: str, transcript: Sequence[Exchange]) -> Grade:
        messages: list[BaseMessage] = [
            SystemMessage(content=judge_system_prompt(GradeDto.model_json_schema())),
            HumanMessage(content=judge_request(criterion, transcript)),
        ]
        logger.debug(f"judge criterion: {criterion}")
        try:
            graded = await invoke_structured(self._model, GradeDto, messages)
        except Exception as exception:
            raise JudgeUnavailable(f"{type(exception).__name__}: {exception}") from exception
        if graded is None:
            raise JudgeUnavailable("the judge's reply could not be read as a grade")
        logger.debug(f"judge grade {graded.score:.2f}: {graded.reason}")
        return Grade(graded.score, graded.reason)
