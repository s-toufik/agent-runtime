from agent_runtime.adapter.outbound.llm.langchain.plan_request import REQUEST_PLAN
from agent_runtime.adapter.outbound.llm.langchain.prompts.agent_roster import agent_roster
from agent_runtime.adapter.outbound.llm.langchain.prompts.clock import utc_now
from agent_runtime.adapter.outbound.llm.langchain.prompts.prompt_book import (
    PromptBook,
    SystemTemplate,
)
from agent_runtime.adapter.outbound.llm.langchain.prompts.tool_catalog import tool_catalog
from agent_runtime.domain.agent.peer_agent import PeerAgent
from agent_runtime.domain.tool.tool_specification import ToolSpecification
from agent_runtime.domain.turn.plan_progress import PlanProgress
from agent_runtime.domain.turn.prior_run import PriorRun
from agent_runtime.domain.workflow.step import Step

_SYSTEM = """\
You are {identity}.
Be brief. Use only facts from tool results or from this conversation. Never invent data.
The earlier messages in this chat are your past exchanges with this user: rely on them
when the user refers to what was said before (their name, a previous question, whether
you talked already).

Request: {request}

Your tools (run only as part of a plan the user approved):
{tools}
{agents}
{mode}

Answer in well-structured Markdown

{diagrams}

Current UTC time: {now}"""

_DIAGRAMS = """\
When a flow, an architecture or how parts connect is easier to see than to read, add a
plain-text diagram in a ```text block (never Mermaid). Skip it for simple answers.
- Draw with box-drawing lines (─ │ ┌ ┐ └ ┘ ├ ┤ ┬ ┴ ┼) and the arrows ► ◄ ▲ ▼.
  Never use ▶ or ◀: they render as emoji and break the alignment.
- Put branches of the same node in the same column, label arrows when the link needs a
  name, and keep lines under 80 characters.
Example:
```text
              ┌─ SQL ──────► PostgreSQL
  Your app ───┼─ events ───► Kafka
              └─ OTLP ─────► OTel Collector ──► Grafana
```"""

_EXECUTE = """\
The user approved this plan. Carry it out one step at a time with your tools.
Progress (✓ done, → current, · to do):
{progress}
{prior}
How to work:
- A tool you call directly returns its whole result into your context: fine for a few
  rows or one value, not for large data. For heavy work, use the tool whose description
  says it keeps results out of your context, and follow its description.
- The working directory is your file storage: save large results there and read
  them back later. Use paths relative to it (e.g. "report.md"): they name the same
  file in your code and in tool calls. Give the file path in your answer.
- To show a plot in a Markdown report, save the image in the working directory and
  link it from the report: ![Title](plot.svg)."""

_FINISHED = """\
All steps of the approved plan are done:
{progress}
{prior}
Answer the request from the tool results. Give the path of every file you wrote."""

_CARRY_ON = """\
Every step of the approved plan has run, but its work was cut off at the step limit:
{progress}
{prior}
Carry on with your tools until the request is done, then answer from the tool results.
Give the path of every file you wrote."""

_PRIOR = """
The plan was paused at the step limit and resumed in this turn. These tool calls ran
before it stopped: do not redo their work, carry on from where they left off.
{actions}
"""

_NEXT_STEP = """\
Now do step {number}: {action}
Call {tool} to do it. Do not describe the step instead of running it."""

_DIRECT = f"""\
You cannot run tools in this reply. Answer from the conversation and general knowledge.
Questions about your tools or what you can do are answered from the list above.
Only if the answer needs to run one of your tools, call {REQUEST_PLAN} instead of answering."""

_DIRECT_ONLY = """\
You cannot run tools in this reply, and you do not write plans. Answer from the conversation
and general knowledge. When the answer needs data or actions you cannot reach, say so plainly
and say what would be needed."""

_FEEDBACK = """\
A reviewer rejected your last answer.

Critique:
{critique}

Write the corrected answer. Fix only what the critique flags."""


SYSTEM: SystemTemplate = SystemTemplate(
    _SYSTEM,
    known=frozenset({"request", "tools", "agents", "mode", "diagrams", "now"}),
    required=frozenset({"mode"}),
)


def act_system_prompt(
    book: PromptBook,
    request: str,
    progress: PlanProgress | None,
    tools: list[ToolSpecification],
    prior: PriorRun | None = None,
    can_plan: bool = True,
    peers: tuple[PeerAgent, ...] = (),
) -> str:
    return book.system(
        Step.ACT,
        request=request,
        tools=tool_catalog(tools),
        agents=agent_roster(peers),
        mode=_mode(progress, prior, can_plan),
        diagrams=_DIAGRAMS,
        now=utc_now(),
    )


def act_feedback(critique: str) -> str:
    return _FEEDBACK.format(critique=critique)


def next_step_request(progress: PlanProgress) -> str | None:
    step = progress.current
    if step is None:
        return None
    return _NEXT_STEP.format(number=progress.number, action=step.action, tool=step.tool)


def _mode(progress: PlanProgress | None, prior: PriorRun | None, can_plan: bool) -> str:
    if progress is None:
        return _DIRECT if can_plan else _DIRECT_ONLY
    return _template(progress, prior).format(progress=progress.render(), prior=_prior(prior))


def _template(progress: PlanProgress, prior: PriorRun | None) -> str:
    if not progress.is_complete:
        return _EXECUTE
    if prior is not None and prior.done >= len(progress.plan.steps):
        return _CARRY_ON
    return _FINISHED


def _prior(prior: PriorRun | None) -> str:
    if prior is None:
        return ""
    actions = "\n".join(f"- {line}" for line in prior.render_actions()) or "(none)"
    return _PRIOR.format(actions=actions)
