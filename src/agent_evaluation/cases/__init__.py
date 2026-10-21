from types import ModuleType

from agent_evaluation.cases import (
    case_guardrail,
    case_memory,
    case_planning,
    case_quality,
    case_relevance,
    case_routing,
    case_security,
    case_task_completion,
    case_tool_selection,
)
from agent_evaluation.domain.case import Case
from agent_evaluation.domain.kind import Kind

MODULES: tuple[ModuleType, ...] = (
    case_tool_selection,
    case_security,
    case_guardrail,
    case_task_completion,
    case_memory,
    case_relevance,
    case_planning,
    case_routing,
    case_quality,
)

CATALOG: dict[Kind, tuple[Case, ...]] = {module.KIND: module.CASES for module in MODULES}
