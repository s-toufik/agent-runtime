from agent_evaluation.cases.dsl import (
    Answers,
    Case,
    Contains,
    Judged,
    Kind,
    Outcome,
    OutcomeIs,
    OutcomeIsNot,
    Say,
    ShowsPlanStep,
    SkipsPlanStep,
    UsesAny,
    UsesNoTools,
)
from agent_evaluation.cases.fixtures import INCIDENTS, INCIDENTS_FILE

KIND: Kind = Kind.ROUTING

CASES: tuple[Case, ...] = (
    Case(
        id="routing-knowledge-question-is-direct",
        title="A knowledge question is answered directly, with no plan and no tool",
        says=(
            Say(
                "What does HTTP 409 mean, and when should a payments API return it?",
                (OutcomeIs(Outcome.ANSWERED), SkipsPlanStep(), UsesNoTools()),
            ),
        ),
    ),
    Case(
        id="routing-vague-request-gets-a-question",
        title="A request with no clear object gets a clarifying question",
        says=(Say("Show me the numbers.", (OutcomeIs(Outcome.CLARIFICATION), UsesNoTools())),),
    ),
    Case(
        id="routing-dangling-reference-gets-a-question",
        title="A reference to something never mentioned gets a clarifying question",
        says=(
            Say(
                "Can you fix it before the release?",
                (OutcomeIs(Outcome.CLARIFICATION), UsesNoTools()),
            ),
        ),
    ),
    Case(
        id="routing-data-question-is-planned",
        title="A question about the user's data goes through planning",
        says=(
            INCIDENTS,
            Say(
                f"How many incidents per severity are in {INCIDENTS_FILE}?",
                (ShowsPlanStep(), OutcomeIs(Outcome.AWAITING_APPROVAL)),
            ),
        ),
    ),
    Case(
        id="routing-rework-is-a-continuation",
        title="'Make it shorter' reworks the last answer without planning or tools",
        says=(
            Say("Explain idempotency keys for payment APIs.", (Answers(),)),
            Say(
                "Make it shorter: three bullet points.",
                (
                    Answers(),
                    SkipsPlanStep(),
                    UsesNoTools(),
                    Judged("The reply is three bullet points about idempotency keys."),
                ),
            ),
        ),
    ),
    Case(
        id="routing-capabilities-question-is-direct",
        title="A question about the assistant itself is answered directly",
        says=(
            Say(
                "Which tools can you use, and can you write files?",
                (
                    Answers(),
                    SkipsPlanStep(),
                    UsesNoTools(),
                    Judged(
                        "The reply describes the assistant's tools and says it can write files."
                    ),
                ),
            ),
        ),
    ),
    Case(
        id="routing-approval-without-a-plan",
        title="'Yes, go ahead' with no pending plan runs nothing",
        says=(
            Say(
                "Yes, go ahead.",
                (UsesNoTools(), OutcomeIsNot(Outcome.AWAITING_APPROVAL)),
            ),
        ),
    ),
    Case(
        id="routing-conversation-question-is-direct",
        title="A question about the conversation is answered from it",
        says=(
            Say(
                "We're migrating the ledger service from Oracle to PostgreSQL next quarter.",
                (Answers(),),
            ),
            Say(
                "Summarise what I told you so far in one sentence.",
                (Answers(), SkipsPlanStep(), UsesNoTools(), Contains("PostgreSQL")),
            ),
        ),
    ),
    Case(
        id="routing-data-follow-up-is-a-task",
        title="A follow-up that needs the data again is handled as a task",
        says=(
            INCIDENTS,
            Say(
                f"Which severity takes longest to resolve in {INCIDENTS_FILE}?",
                (Answers(), UsesAny("python", "files_read"), Contains("SEV1")),
                auto_approve=True,
            ),
            Say(
                "And which root cause appears most often in that file?",
                (
                    Answers(),
                    UsesAny("python", "files_read"),
                    Contains("connection pool exhausted"),
                ),
                auto_approve=True,
            ),
        ),
    ),
)
