import re
from dataclasses import dataclass

from agent_evaluation.domain.check.check import CheckContext, CheckResult

_FLAGS: re.RegexFlag = re.IGNORECASE | re.MULTILINE


def _quoted(texts: tuple[str, ...]) -> str:
    return ", ".join(f'"{text}"' for text in texts)


@dataclass(frozen=True, slots=True, init=False)
class Contains:
    texts: tuple[str, ...]

    def __init__(self, *texts: str) -> None:
        object.__setattr__(self, "texts", texts)

    @property
    def label(self) -> str:
        return f"answer contains {_quoted(self.texts)}"

    async def verify(self, context: CheckContext) -> CheckResult:
        content = context.reply.content.casefold()
        missing = tuple(
            text for text in map(context.render, self.texts) if text.casefold() not in content
        )
        detail = f"missing {_quoted(missing)}" if missing else ""
        return CheckResult(self.label, not missing, detail)


@dataclass(frozen=True, slots=True, init=False)
class ContainsAny:
    texts: tuple[str, ...]

    def __init__(self, *texts: str) -> None:
        object.__setattr__(self, "texts", texts)

    @property
    def label(self) -> str:
        return f"answer contains one of {_quoted(self.texts)}"

    async def verify(self, context: CheckContext) -> CheckResult:
        content = context.reply.content.casefold()
        passed = any(text.casefold() in content for text in map(context.render, self.texts))
        return CheckResult(self.label, passed, "" if passed else "none of them found")


@dataclass(frozen=True, slots=True, init=False)
class NotContains:
    texts: tuple[str, ...]

    def __init__(self, *texts: str) -> None:
        object.__setattr__(self, "texts", texts)

    @property
    def label(self) -> str:
        return f"answer does not contain {_quoted(self.texts)}"

    async def verify(self, context: CheckContext) -> CheckResult:
        content = context.reply.content.casefold()
        found = tuple(
            text for text in map(context.render, self.texts) if text.casefold() in content
        )
        detail = f"found {_quoted(found)}" if found else ""
        return CheckResult(self.label, not found, detail)


@dataclass(frozen=True, slots=True)
class Matches:
    pattern: str

    @property
    def label(self) -> str:
        return f"answer matches /{self.pattern}/"

    async def verify(self, context: CheckContext) -> CheckResult:
        found = re.search(context.render(self.pattern), context.reply.content, _FLAGS)
        return CheckResult(self.label, found is not None, "" if found else "no match")


@dataclass(frozen=True, slots=True)
class NotMatches:
    pattern: str

    @property
    def label(self) -> str:
        return f"answer does not match /{self.pattern}/"

    async def verify(self, context: CheckContext) -> CheckResult:
        found = re.search(context.render(self.pattern), context.reply.content, _FLAGS)
        return CheckResult(self.label, found is None, f'found "{found.group(0)}"' if found else "")
