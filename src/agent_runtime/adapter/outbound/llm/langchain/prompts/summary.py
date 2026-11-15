from agent_runtime.adapter.outbound.llm.langchain.prompts.prompt_book import (
    PromptBook,
    SystemTemplate,
)
from agent_runtime.domain.workflow.step import Step

_SYSTEM = """\
You keep a running summary of a conversation between a user and an assistant.
Merge the existing summary with the new messages.
Keep facts, figures, file paths, decisions and open questions. Drop small talk.
At most 200 words. Plain text only."""

_REQUEST = """\
Existing summary:
{summary}

New messages:
{messages}"""


SYSTEM: SystemTemplate = SystemTemplate(_SYSTEM, known=frozenset())


def summary_system_prompt(book: PromptBook) -> str:
    return book.system(Step.SUMMARIZE)


def summary_request(summary: str, messages: str) -> str:
    return _REQUEST.format(summary=summary or "(none)", messages=messages)
