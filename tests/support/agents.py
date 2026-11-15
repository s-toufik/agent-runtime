from pathlib import Path

from agent_runtime.adapter.outbound.llm.langchain.prompts.generic_prompts import prompt_book
from agent_runtime.adapter.outbound.llm.langchain.prompts.prompt_book import PromptBook
from agent_runtime.domain.agent.agent import Agent
from agent_runtime.domain.agent.agent_skill import AgentSkill

IDENTITY: str = "the homelab test assistant"
SKILL: AgentSkill = AgentSkill(
    id="answer",
    name="Answer",
    description="Answers questions about the homelab.",
    tags=("homelab",),
    examples=("Which pods restarted?",),
)
AGENT: Agent = Agent(name="agent-runtime", description=IDENTITY, skills=(SKILL,))
PROMPTS: PromptBook = prompt_book(IDENTITY)

TEST_AGENTS: Path = Path(__file__).resolve().parent / "agents"
TEST_AGENT: str = "assistant"
GUARDED_TEST_AGENT: str = "guarded"
