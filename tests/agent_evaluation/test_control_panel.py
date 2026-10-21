import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_evaluation.bootstrap.cli import DEFAULT_PANEL, main
from agent_evaluation.bootstrap.container import ConfigurationError, EvaluationContainer
from agent_evaluation.cases import CATALOG
from agent_evaluation.configuration.control_panel import ControlPanel
from agent_evaluation.configuration.overrides import Overrides
from agent_evaluation.domain.case import Case, Say
from agent_evaluation.domain.kind import Kind


def _panel(**changes) -> dict:
    raw = json.loads(DEFAULT_PANEL.read_text(encoding="utf-8"))
    for key, value in changes.items():
        raw[key] = {**raw.get(key, {}), **value}
    return raw


def _write(tmp_path: Path, raw: dict) -> Path:
    path = tmp_path / "panel.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def test_the_default_panel_loads_and_covers_every_kind_and_capability() -> None:
    panel = ControlPanel.load(DEFAULT_PANEL)

    assert set(panel.kinds) == set(Kind)
    EvaluationContainer(panel, DEFAULT_PANEL, Overrides(), CATALOG).validate()


def test_a_typo_in_the_panel_is_rejected(tmp_path) -> None:
    path = _write(tmp_path, _panel(run={"runz": 3}))

    with pytest.raises(ValidationError, match="runz"):
        ControlPanel.load(path)


def test_overrides_replace_the_agent_and_force_runs_and_pauses() -> None:
    overrides = Overrides(
        kinds=(Kind.MEMORY,), runs=1, pause_between_runs_seconds=0, agent_url="http://other:9"
    )
    panel = overrides.apply(ControlPanel.load(DEFAULT_PANEL))

    (suite,) = EvaluationContainer(panel, DEFAULT_PANEL, overrides, CATALOG).suites()

    assert panel.agent.base_url == "http://other:9" and suite.kind is Kind.MEMORY
    case = suite.cases[0]
    assert suite.policy.for_case(case).runs == 1
    assert suite.policy.for_case(case).pause_between_runs_seconds == 0


def test_kind_settings_override_the_run_defaults() -> None:
    panel = ControlPanel.load(DEFAULT_PANEL)

    suites = EvaluationContainer(panel, DEFAULT_PANEL, Overrides(), CATALOG).suites()

    security = next(suite for suite in suites if suite.kind is Kind.SECURITY)
    assert security.policy.runs == panel.kinds[Kind.SECURITY].runs
    assert security.policy.runs != panel.run.runs


def test_case_patterns_select_cases_across_kinds() -> None:
    overrides = Overrides(cases=("memory-*",))
    panel = ControlPanel.load(DEFAULT_PANEL)

    suites = EvaluationContainer(panel, DEFAULT_PANEL, overrides, CATALOG).suites()

    assert [suite.kind for suite in suites] == [Kind.MEMORY]
    assert all(case.id.startswith("memory-") for case in suites[0].cases)


def test_a_case_using_an_unknown_capability_is_reported() -> None:
    catalog = {Kind.QUALITY: (Case("x", "X", (Say("?"),), requires=("salesforce",)),)}
    container = EvaluationContainer(
        ControlPanel.load(DEFAULT_PANEL), DEFAULT_PANEL, Overrides(), catalog
    )

    with pytest.raises(ConfigurationError, match="salesforce"):
        container.validate()


def test_a_dry_run_lists_the_plan_without_calling_the_agent(capsys) -> None:
    assert main(["--dry-run", "--kinds", "guardrail,routing", "--runs", "2"]) == 0

    out = capsys.readouterr().out
    assert "GUARDRAIL:" in out and "ROUTING:" in out and "MEMORY:" not in out
    assert "skipped: needs guardrail (not available)" in out
    assert "Total:" in out


def test_an_unusable_panel_exits_with_code_2(tmp_path, capsys) -> None:
    path = _write(tmp_path, {"agent": {}})

    assert main(["--panel", str(path), "--dry-run"]) == 2
    assert "not usable" in capsys.readouterr().err
