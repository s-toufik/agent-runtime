import pytest

from agent_evaluation.adapter.judge.langchain_judge import GradeDto, LangChainJudge
from agent_evaluation.domain.exception import JudgeUnavailable
from agent_evaluation.domain.exchange import Exchange
from tests.agent_evaluation.fakes import reply
from tests.agent_runtime.adapter.outbound.llm.langchain.fakes import FakeLLM

TRANSCRIPT = (Exchange("main", "Capital of France?", False, reply("Paris", tools=("echo",))),)


async def test_the_judge_grades_with_the_criterion_and_the_conversation() -> None:
    llm = FakeLLM(parsed=[GradeDto(score=0.9, reason="It says Paris.")])

    grade = await LangChainJudge(llm).grade("Names the capital.", TRANSCRIPT)  # ty: ignore[invalid-argument-type]

    assert (grade.score, grade.reason) == (0.9, "It says Paris.")
    prompt = llm.prompt()
    assert "Names the capital." in prompt and "Capital of France?" in prompt
    assert "tools used: echo" in prompt and "Return only this JSON" in prompt


async def test_an_unreadable_grade_or_a_failing_call_makes_the_judge_unavailable() -> None:
    unreadable = LangChainJudge(FakeLLM(parsed=[None]))  # ty: ignore[invalid-argument-type]
    failing = LangChainJudge(FakeLLM(parsed=[]))  # ty: ignore[invalid-argument-type]

    with pytest.raises(JudgeUnavailable, match="could not be read"):
        await unreadable.grade("x", TRANSCRIPT)
    with pytest.raises(JudgeUnavailable, match="IndexError"):
        await failing.grade("x", TRANSCRIPT)


def test_the_judge_is_built_with_the_agents_llm_chat() -> None:
    judge = LangChainJudge.from_settings(
        base_url="http://llm:9000/v1",
        api_key="secret",
        model_name="judge-model",
        temperature=0.0,
        max_output_tokens=512,
        max_context_tokens=8000,
        timeout_seconds=45,
        reasoning_effort="low",
    )

    model = judge._model
    assert model.model_name == "judge-model" and model.max_retries == 0  # ty: ignore[unresolved-attribute]
    assert model.request_timeout == 45  # ty: ignore[unresolved-attribute]
