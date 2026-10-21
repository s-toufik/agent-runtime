from agent_runtime.adapter.outbound.langgraph.node.agent_node import AgentNode
from agent_runtime.domain.workflow.step import Step


class PlanNode(AgentNode):
    step = Step.PLAN
