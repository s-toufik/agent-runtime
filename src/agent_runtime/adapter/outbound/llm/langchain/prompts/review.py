_SYSTEM = """\
You check if an assistant's answer is right for what the user wants.

The request and its success criteria are an interpretation of the user's latest message.
The recent conversation is the ground truth: if the interpretation contradicts it, judge
the answer against what the user meant in the conversation.

- Accept if the answer gives the user what they asked for and its logic holds.
- Retry if it misses what the user asked for.
- Retry if it says it did something (ran code, wrote or changed a file) that the tool
  calls do not show, or that failed.
{grounding}
- Do not reject for style or wording.
- Keep the critique short and concrete: what to fix.

Return only this JSON, nothing else:
{output_format}"""

_REQUEST = """\
Recent conversation (ends with the user's latest message):
{conversation}

Request, as interpreted:
{request}

Success criteria:
{criteria}

Approved plan, with its progress (✓ done, → current, · to do):
{plan}

Tool calls made:
{actions}
{prior}
Tool evidence:
{evidence}

Answer to check:
{answer}"""


_PRIOR = """
Tool calls made for this plan in earlier turns, before it was paused (their outcomes are
evidence too):
{actions}
"""

_WITH_EVIDENCE = """\
- Retry if it contradicts the tool evidence, or states data (numbers, records, file
  contents) that is not in the tool evidence."""

_WITHOUT_EVIDENCE = """\
- No tool ran: the answer may use general knowledge and the conversation. Retry only if
  it is wrong, or states the user's own data (numbers, records, file contents) that the
  conversation does not give."""


def reflection_system_prompt(output_format: object, has_evidence: bool) -> str:
    grounding = _WITH_EVIDENCE if has_evidence else _WITHOUT_EVIDENCE
    return _SYSTEM.format(output_format=output_format, grounding=grounding)


def reflection_request(
    conversation: str,
    request: str,
    criteria: list[str],
    plan: str | None,
    actions: list[str],
    evidence: list[str],
    answer: str,
    prior_actions: list[str] | None = None,
) -> str:
    return _REQUEST.format(
        conversation=conversation,
        request=request,
        criteria=_bullets(criteria) or "(none)",
        plan=plan or "(none)",
        actions=_bullets(actions) or "(none)",
        prior=_PRIOR.format(actions=_bullets(prior_actions)) if prior_actions else "",
        evidence="\n---\n".join(evidence) or "(none)",
        answer=answer or "(empty answer)",
    )


def _bullets(lines: list[str]) -> str:
    return "\n".join(f"- {line}" for line in lines)
