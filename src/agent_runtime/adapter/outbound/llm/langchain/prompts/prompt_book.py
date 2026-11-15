from collections.abc import Mapping
from dataclasses import dataclass
from string import Formatter
from typing import Any

from agent_runtime.domain.agent.agent_prompts import AgentPrompts
from agent_runtime.domain.workflow.step import Step

IDENTITY: str = "identity"


@dataclass(frozen=True, slots=True)
class SystemTemplate:
    text: str
    known: frozenset[str]
    required: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        _check("the generic", self.text, self)


class PromptBook:
    def __init__(
        self,
        identity: str,
        defaults: Mapping[Step, SystemTemplate],
        prompts: AgentPrompts | None = None,
    ) -> None:
        self._identity = identity
        self._texts: dict[Step, str] = {}
        overrides: AgentPrompts = prompts or AgentPrompts()
        for step, template in defaults.items():
            text: str | None = overrides.for_step(step)
            if text is not None:
                _check(f"the agent's {step.value}", text, template)
            self._texts[step] = text if text is not None else template.text
        unknown = set(overrides.by_step) - set(defaults)
        if unknown:
            raise ValueError(f"no system prompt is used for {', '.join(sorted(unknown))}")

    def system(self, step: Step, **values: Any) -> str:
        return self._texts[step].format(**{IDENTITY: self._identity, **values})


def _placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in Formatter().parse(text) if name is not None}


def _check(owner: str, text: str, template: SystemTemplate) -> None:
    names: set[str] = _placeholders(text)
    unknown: set[str] = names - template.known - {IDENTITY}
    if unknown:
        raise ValueError(
            f"{owner} prompt uses {_braced(unknown)}; it may use {_braced(template.known | {IDENTITY})}"
        )
    missing: set[str] = set(template.required) - names
    if missing:
        raise ValueError(f"{owner} prompt must use {_braced(missing)}")


def _braced(names: set[str] | frozenset[str]) -> str:
    return ", ".join(f"{{{name}}}" for name in sorted(names))
