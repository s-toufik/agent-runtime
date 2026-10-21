from dataclasses import dataclass

from agent_evaluation.domain.reply import AgentReply


@dataclass(frozen=True, slots=True)
class Exchange:
    conversation: str
    message: str
    auto_approve: bool
    reply: AgentReply
