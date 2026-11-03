from dataclasses import dataclass

from agent_evaluation.domain.check.check import CheckContext, CheckResult


def _used(context: CheckContext) -> str:
    return f"tools used: {', '.join(context.reply.tools) or 'none'}"


@dataclass(frozen=True, slots=True, init=False)
class UsesAny:
    capabilities: tuple[str, ...]

    def __init__(self, *capabilities: str) -> None:
        object.__setattr__(self, "capabilities", capabilities)

    @property
    def label(self) -> str:
        return f"uses {' or '.join(self.capabilities)}"

    async def verify(self, context: CheckContext) -> CheckResult:
        capabilities = context.rules.capabilities
        passed = any(
            capabilities.provided_by(tool, self.capabilities) for tool in context.reply.tools
        )
        return CheckResult(self.label, passed, _used(context))


@dataclass(frozen=True, slots=True, init=False)
class UsesAll:
    capabilities: tuple[str, ...]

    def __init__(self, *capabilities: str) -> None:
        object.__setattr__(self, "capabilities", capabilities)

    @property
    def label(self) -> str:
        return f"uses {' and '.join(self.capabilities)}"

    async def verify(self, context: CheckContext) -> CheckResult:
        capabilities = context.rules.capabilities
        passed = all(
            any(capabilities[name].provides(tool) for tool in context.reply.tools)
            for name in self.capabilities
        )
        return CheckResult(self.label, passed, _used(context))


@dataclass(frozen=True, slots=True, init=False)
class Avoids:
    capabilities: tuple[str, ...]

    def __init__(self, *capabilities: str) -> None:
        object.__setattr__(self, "capabilities", capabilities)

    @property
    def label(self) -> str:
        return f"does not use {' or '.join(self.capabilities)}"

    async def verify(self, context: CheckContext) -> CheckResult:
        capabilities = context.rules.capabilities
        passed = not any(
            capabilities.provided_by(tool, self.capabilities) for tool in context.reply.tools
        )
        return CheckResult(self.label, passed, _used(context))


@dataclass(frozen=True, slots=True)
class UsesNoTools:
    @property
    def label(self) -> str:
        return "uses no tools"

    async def verify(self, context: CheckContext) -> CheckResult:
        return CheckResult(self.label, not context.reply.tools, _used(context))
