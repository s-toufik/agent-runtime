from tests.architecture.test_boundaries import FRAMEWORKS, PACKAGE, SOURCE, _imports, _violations

EVALUATION = SOURCE / "agent_evaluation"
LLM_ADAPTER = "agent_runtime.adapter.outbound.llm"


def test_the_evaluation_domain_is_free_of_frameworks_and_outer_layers() -> None:
    forbidden = FRAMEWORKS | {
        "agent_runtime",
        "agent_evaluation.application",
        "agent_evaluation.adapter",
        "agent_evaluation.configuration",
        "agent_evaluation.bootstrap",
        "agent_evaluation.cases",
    }
    assert _violations(EVALUATION / "domain", forbidden) == []


def test_the_evaluation_application_depends_only_on_its_domain() -> None:
    forbidden = FRAMEWORKS | {
        "agent_runtime",
        "agent_evaluation.adapter",
        "agent_evaluation.configuration",
        "agent_evaluation.bootstrap",
        "agent_evaluation.cases",
    }
    assert _violations(EVALUATION / "application", forbidden) == []


def test_cases_are_written_only_with_the_evaluation_domain() -> None:
    forbidden = FRAMEWORKS | {
        "agent_runtime",
        "agent_evaluation.application",
        "agent_evaluation.adapter",
        "agent_evaluation.bootstrap",
    }
    assert _violations(EVALUATION / "cases", forbidden) == []


def test_only_the_judge_reuses_the_agent_and_only_its_llm_adapter() -> None:
    reused = {
        f"{path.relative_to(SOURCE)} imports {module}"
        for path, modules in _imports(EVALUATION).items()
        for module in modules
        if module.startswith("agent_runtime")
    }

    assert reused, "the judge is expected to reuse the agent's LLMChat"
    assert all("agent_evaluation/adapter/judge/" in line for line in reused), reused
    assert all(f"imports {LLM_ADAPTER}." in line for line in reused), reused


def test_the_evaluation_never_reaches_the_agents_wiring_or_graph() -> None:
    assert _violations(EVALUATION, {"bootstrap", "langgraph"}) == []


def test_the_agent_never_imports_the_evaluation() -> None:
    assert _violations(PACKAGE, {"agent_evaluation"}) == []
