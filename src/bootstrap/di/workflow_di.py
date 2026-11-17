from functools import cached_property
from typing import Any

from pycraftcore.logger.port import Logger

from agent_runtime.adapter.outbound.langgraph.graph.agent_graph_builder import (
    AgentGraphBuilder,
)
from agent_runtime.adapter.outbound.langgraph.graph.policy_router import PolicyRouter
from agent_runtime.adapter.outbound.langgraph.langgraph_event_publisher import (
    LangGraphEventPublisher,
)
from agent_runtime.adapter.outbound.langgraph.langgraph_workflow_runner import (
    LangGraphWorkflowRunner,
)
from agent_runtime.adapter.outbound.langgraph.node.agent_node import AgentNode
from agent_runtime.adapter.outbound.langgraph.node.agent_nodes import agent_nodes
from agent_runtime.adapter.outbound.langgraph.state.turn_state_codec import TurnStateCodec
from agent_runtime.adapter.outbound.llm.enum.answer_delivery import AnswerDelivery
from agent_runtime.adapter.outbound.llm.langchain.actor import LangChainActor
from agent_runtime.adapter.outbound.llm.langchain.chat_models import ChatModels
from agent_runtime.adapter.outbound.llm.langchain.context_window import ContextWindow
from agent_runtime.adapter.outbound.llm.langchain.guard import LangChainGuard
from agent_runtime.adapter.outbound.llm.langchain.intent_classifier import (
    LangChainIntentClassifier,
)
from agent_runtime.adapter.outbound.llm.langchain.planner import LangChainPlanner
from agent_runtime.adapter.outbound.llm.langchain.prompts.prompt_book import PromptBook
from agent_runtime.adapter.outbound.llm.langchain.reply.reply_reader import ReplyReader
from agent_runtime.adapter.outbound.llm.langchain.reply.streamed_reply import StreamedReply
from agent_runtime.adapter.outbound.llm.langchain.reply.whole_reply import WholeReply
from agent_runtime.adapter.outbound.llm.langchain.reviewer import LangChainReviewer
from agent_runtime.adapter.outbound.llm.langchain.summarizer import LangChainSummarizer
from agent_runtime.adapter.outbound.llm.langchain.token_counter import (
    EstimatedTokenCounter,
)
from agent_runtime.adapter.outbound.llm.langchain.usage_meter import LangChainUsageMeter
from agent_runtime.adapter.outbound.tool.toolbox import Toolbox
from agent_runtime.application.port.outbound.turn_event_publisher import TurnEventPublisher
from agent_runtime.application.port.outbound.workflow_runner import WorkflowRunner
from agent_runtime.application.step.act_step import ActStep
from agent_runtime.application.step.clarify_step import ClarifyStep
from agent_runtime.application.step.feedback_step import FeedbackStep
from agent_runtime.application.step.finish_step import FinishStep
from agent_runtime.application.step.plan_step import PlanStep
from agent_runtime.application.step.review_step import ReviewStep
from agent_runtime.application.step.run_tools_step import RunToolsStep
from agent_runtime.application.step.screen_step import ScreenStep
from agent_runtime.application.step.step_handler import StepHandler
from agent_runtime.application.step.summarize_step import SummarizeStep
from agent_runtime.application.step.understand_step import UnderstandStep
from agent_runtime.domain.workflow.step import Step
from agent_runtime.domain.workflow.turn_policy import TurnPolicy
from agent_runtime.domain.workflow.turn_shape import TurnShape


class WorkflowDI:
    def __init__(
        self,
        models: ChatModels,
        logger: Logger,
        *,
        answer_delivery: AnswerDelivery,
        prompts: PromptBook,
        shape: TurnShape,
    ) -> None:
        self._prompts = prompts
        self._policy = TurnPolicy(shape)
        self._models = models
        self._logger = logger
        self._answer_delivery = answer_delivery

    @cached_property
    def turn_events(self) -> TurnEventPublisher:
        return LangGraphEventPublisher()

    def runner(self, toolbox: Toolbox, checkpointer: Any) -> WorkflowRunner:
        return LangGraphWorkflowRunner(
            self.graph(toolbox, checkpointer), self._logger, LangChainUsageMeter()
        )

    def graph(self, toolbox: Toolbox, checkpointer: Any) -> Any:
        codec: TurnStateCodec = TurnStateCodec()
        policy: TurnPolicy = self._policy
        nodes: list[AgentNode] = agent_nodes(self.steps(toolbox), codec, self.turn_events)
        return AgentGraphBuilder(nodes, policy, PolicyRouter(policy, codec)).build(checkpointer)

    def steps(self, toolbox: Toolbox) -> list[StepHandler]:
        models, window, logger = self._models, ContextWindow(), self._logger
        prompts = self._prompts
        steps: list[StepHandler] = [
            UnderstandStep(
                LangChainIntentClassifier(models, window, logger, prompts=prompts), logger
            ),
            PlanStep(LangChainPlanner(models, window, logger, prompts=prompts), toolbox),
            ClarifyStep(),
            ActStep(
                LangChainActor(
                    models,
                    window,
                    logger,
                    WholeReply(),
                    self.final_reply(),
                    prompts=prompts,
                    can_plan=self._policy.shape.plan,
                ),
                toolbox,
            ),
            RunToolsStep(toolbox, self.turn_events),
            ReviewStep(LangChainReviewer(models, logger, prompts=prompts), logger),
            FeedbackStep(logger),
            FinishStep(),
            SummarizeStep(
                LangChainSummarizer(models, logger, prompts=prompts),
                EstimatedTokenCounter(),
                logger,
            ),
        ]
        if self._policy.shape.screen:
            steps.append(ScreenStep(LangChainGuard(models, logger, prompts=prompts), logger))
        reachable: set[Step] = set(self._policy.steps())
        return [handler for handler in steps if handler.step in reachable]

    def final_reply(self) -> ReplyReader:
        match self._answer_delivery:
            case AnswerDelivery.STREAM:
                return StreamedReply(self.turn_events)
            case AnswerDelivery.WHOLE:
                return WholeReply()
