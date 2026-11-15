from agent_runtime.domain.turn.turn import Turn
from agent_runtime.domain.workflow.conditions import (
    Condition,
    answers_directly,
    any_of,
    asks_for_plan_without_one,
    asks_for_tools,
    has_approved_plan,
    is_ambiguous,
    is_plain_direct_answer,
    leaves_plan_unfinished,
    needs_plan,
    ran_out_of_steps,
    retry_allowed,
)
from agent_runtime.domain.workflow.step import Step
from agent_runtime.domain.workflow.transition import Transition
from agent_runtime.domain.workflow.turn_shape import TurnShape

FIRST_STEP: Step = Step.UNDERSTAND


class TurnPolicy:
    def __init__(self, shape: TurnShape | None = None, screen: bool = False) -> None:
        self.shape: TurnShape = shape or TurnShape()
        self.TRANSITIONS: tuple[Transition, ...] = self._transitions(self.shape, screen)

    @staticmethod
    def _transitions(shape: TurnShape, screen: bool) -> tuple[Transition, ...]:
        return (
            *_understanding(shape),
            *(_planning(screen) if shape.plan else ()),
            *((Transition(Step.CLARIFY, Step.FINISH),) if shape.clarify else ()),
            *_acting(shape),
            *(
                (
                    Transition(Step.REVIEW, Step.FEEDBACK, retry_allowed),
                    Transition(Step.REVIEW, Step.FINISH),
                    Transition(Step.FEEDBACK, Step.ACT),
                )
                if shape.review
                else ()
            ),
            Transition(Step.FINISH, Step.SUMMARIZE),
            Transition(Step.SUMMARIZE, Step.END),
        )

    def next(self, done: Step, turn: Turn) -> Step:
        for transition in self.TRANSITIONS:
            if transition.source is done and transition.when(turn):
                return transition.target
        raise ValueError(f"No transition leaves the step '{done}'")

    def targets(self, source: Step) -> list[Step]:
        return list(dict.fromkeys(t.target for t in self.TRANSITIONS if t.source is source))

    def steps(self) -> list[Step]:
        reached: list[Step] = [FIRST_STEP]
        for step in reached:
            for target in self.targets(step):
                if target is not Step.END and target not in reached:
                    reached.append(target)
        return reached


def _understanding(shape: TurnShape) -> tuple[Transition, ...]:
    planned: Condition = needs_plan
    if not shape.direct:
        planned = any_of(needs_plan, answers_directly)
        if not shape.clarify:
            planned = any_of(planned, is_ambiguous)
    return (
        *((Transition(Step.UNDERSTAND, Step.PLAN, planned),) if shape.plan else ()),
        *((Transition(Step.UNDERSTAND, Step.CLARIFY, is_ambiguous),) if shape.clarify else ()),
        Transition(Step.UNDERSTAND, Step.ACT),
    )


def _planning(screen: bool) -> tuple[Transition, ...]:
    if screen:
        return (
            Transition(Step.PLAN, Step.SCREEN),
            Transition(Step.SCREEN, Step.ACT, has_approved_plan),
            Transition(Step.SCREEN, Step.FINISH),
        )
    return (
        Transition(Step.PLAN, Step.ACT, has_approved_plan),
        Transition(Step.PLAN, Step.FINISH),
    )


def _acting(shape: TurnShape) -> tuple[Transition, ...]:
    with_plan: tuple[Transition, ...] = (
        (Transition(Step.ACT, Step.PLAN, asks_for_plan_without_one),) if shape.plan else ()
    )
    tools: tuple[Transition, ...] = (
        (
            Transition(Step.ACT, Step.RUN_TOOLS, asks_for_tools),
            Transition(Step.ACT, Step.ACT, leaves_plan_unfinished),
        )
        if shape.plan
        else ()
    )
    after: tuple[Transition, ...] = (
        (
            Transition(Step.ACT, Step.FINISH, is_plain_direct_answer),
            Transition(Step.ACT, Step.REVIEW),
        )
        if shape.review
        else (Transition(Step.ACT, Step.FINISH),)
    )
    return (
        *with_plan,
        Transition(Step.ACT, Step.FINISH, ran_out_of_steps),
        *tools,
        *after,
        *((Transition(Step.RUN_TOOLS, Step.ACT),) if shape.plan else ()),
    )
