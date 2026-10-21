from agent_runtime.adapter.outbound.llm.langchain.plan_request import REQUEST_PLAN
from agent_runtime.adapter.outbound.llm.langchain.prompts.clock import utc_now
from agent_runtime.adapter.outbound.llm.langchain.prompts.tool_catalog import tool_catalog
from agent_runtime.domain.tool.tool_specification import ToolSpecification
from agent_runtime.domain.turn.plan_progress import PlanProgress

_SYSTEM = """\
You are BlueAI, an assistant for the Blue homelab platform.
Be brief. Use only facts from tool results or from this conversation. Never invent data.
The earlier messages in this chat are your past exchanges with this user: rely on them
when the user refers to what was said before (their name, a previous question, whether
you talked already).

Request: {request}

Your tools (run only as part of a plan the user approved):
{tools}

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

How to work:
- A tool you call directly returns its whole result into your context. Fine for a 
  few rows or one value; a large result set will overflow your context window.
- Inside python_executor every other tool is callable as a Python function (same
  name, keyword arguments). Results of tools you call there stay in the sandbox and 
  do NOT enter your context: only what you assign to 'result' and what you print
  comes back to you.
- So for large or heavy work (many rows, aggregation, joins, statistics), plan a 
  python_executor: fetch and compute inside the script, write the full output to a 
  file (or a Confluence page), and return only a short summary plus the file path or 
  link. This keeps the big data out of your context instead of streaming it through. 
- The working directory is your file storage: save large results there and read
  them back later. Use paths relative to it (e.g. "report.md"): they name the same
  file in your code and in tool calls. Give the file path in your answer.
- To show a plot in a Markdown report, save the image in the working directory and
  link it from the report: ![Title](plot.svg).

Example inside python_executor (heavy analysis only):
    import pandas as pd
    file = file_reader(file_path="eqd_positions.csv")
    df = pd.DataFrame(file["content"]["rows"])
    ... do some analysis ...
    saved = file_writer(file_path="report.md", data=report_text)
    result = saved["path"]"""

_FINISHED = """\
All steps of the approved plan are done:
{progress}

Answer the request from the tool results. Give the path of every file you wrote."""

_NEXT_STEP = """\
Now do step {number}: {action}
Call {tool} to do it. Do not describe the step instead of running it."""

_DIRECT = f"""\
You cannot run tools in this reply. Answer from the conversation and general knowledge.
Questions about your tools or what you can do are answered from the list above.
Only if the answer needs to run one of your tools, call {REQUEST_PLAN} instead of answering."""

_FEEDBACK = """\
A reviewer rejected your last answer.

Critique:
{critique}

Write the corrected answer. Fix only what the critique flags."""


def act_system_prompt(
    request: str, progress: PlanProgress | None, tools: list[ToolSpecification]
) -> str:
    return _SYSTEM.format(
        request=request,
        tools=tool_catalog(tools),
        mode=_mode(progress),
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


def _mode(progress: PlanProgress | None) -> str:
    if progress is None:
        return _DIRECT
    template = _FINISHED if progress.is_complete else _EXECUTE
    return template.format(progress=progress.render())
