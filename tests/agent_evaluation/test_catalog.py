import re
from pathlib import Path

import pytest

from agent_evaluation.cases import CATALOG, MODULES
from agent_evaluation.domain.check.check import RUN_ID
from agent_evaluation.domain.kind import Kind

CASES_DIR: Path = Path(__file__).resolve().parents[2] / "src" / "agent_evaluation" / "cases"


def test_every_kind_has_its_own_case_file_and_cases() -> None:
    assert set(CATALOG) == set(Kind)
    for module in MODULES:
        assert Path(module.__file__ or "").name == f"case_{module.KIND.lower()}.py"
        assert module.CASES, module.KIND


def test_case_ids_are_unique_and_readable() -> None:
    ids = [case.id for cases in CATALOG.values() for case in cases]

    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", case_id) for case_id in ids)


@pytest.mark.parametrize("kind", list(Kind))
def test_every_case_says_something_and_checks_something(kind: Kind) -> None:
    for case in CATALOG[kind]:
        assert case.title and case.says, case.id
        assert all(say.message.strip() for say in case.says), case.id
        assert any(say.expect for say in case.says), case.id


def test_the_run_id_placeholder_is_spelled_right() -> None:
    for cases in CATALOG.values():
        for case in cases:
            for say in case.says:
                placeholders = set(re.findall(r"\{run[^}]*\}", say.message, re.IGNORECASE))
                assert placeholders <= {RUN_ID}, case.id
