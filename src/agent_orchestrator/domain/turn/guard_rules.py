import re

from agent_orchestrator.domain.turn.plan import Plan

_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"|`[^`]*`")

_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\b(drop|truncate)\b.{0,20}\b(table|database|schema)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        "the plan drops or truncates a table or database",
    ),
    (
        re.compile(
            r"\bdelete\b.{0,25}\b(from|rows?|records?|tables?|files?|directory|every file|all files)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        "the plan deletes existing data or files",
    ),
    (
        re.compile(
            r"\b(rm\s+-rf|shutil\.rmtree|os\.remove|os\.unlink|rmdir)\b",
            re.IGNORECASE,
        ),
        "the plan runs a file-deletion command",
    ),
    (
        re.compile(
            r"\b(os\.environ|os\.getenv|environment variables?)\b",
            re.IGNORECASE,
        ),
        "the plan reads environment variables",
    ),
    (
        re.compile(
            r"\b(read|show|print|list|reveal|fetch|collect|dump)\b"
            r".{0,40}\b(secrets?|tokens?|passwords?|credentials?|api[\s_-]?keys?)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        "the plan reads or exposes secrets",
    ),
    (
        re.compile(
            r"\b(secrets?|tokens?|passwords?|credentials?|api[\s_-]?keys?)\b"
            r".{0,40}\b(read|show|print|list|reveal|fetch|collect|dump)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        "the plan reads or exposes secrets",
    ),
    (
        re.compile(
            r"\b(upload|exfiltrate\w*|post|send|transmit)\b"
            r".{0,60}https?://",
            re.IGNORECASE | re.DOTALL,
        ),
        "the plan sends data to an external destination",
    ),
)


def hard_block_reason(plan: Plan) -> str | None:
    text = _QUOTED.sub(" ", plan.render())

    for pattern, reason in _RULES:
        if pattern.search(text):
            return reason

    return None
