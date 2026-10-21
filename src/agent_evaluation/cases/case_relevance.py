from agent_evaluation.cases.dsl import (
    Answers,
    Case,
    Contains,
    Judged,
    Kind,
    Matches,
    Say,
)

KIND: Kind = Kind.RELEVANCE

CASES: tuple[Case, ...] = (
    Case(
        id="relevance-question-buried-in-small-talk",
        title="The actual question is answered despite unrelated remarks around it",
        says=(
            Say(
                "Our office moved to Lyon last week and the coffee machine is broken again, "
                "anyway: which HTTP status code should our API return when a client exceeds "
                "its rate limit, and which header tells it when to retry?",
                (
                    Answers(),
                    Contains("429", "Retry-After"),
                    Judged(
                        "The answer addresses the rate-limit question and does not spend time "
                        "on the office move or the coffee machine."
                    ),
                ),
            ),
        ),
    ),
    Case(
        id="relevance-direct-answer-first",
        title="A precise question gets the precise answer first",
        says=(
            Say(
                "Which SQL transaction isolation level prevents phantom reads?",
                (
                    Answers(),
                    Contains("serializable"),
                    Judged(
                        "The answer names the isolation level in its first sentence or two "
                        "instead of starting with a general lecture."
                    ),
                ),
            ),
        ),
    ),
    Case(
        id="relevance-respects-the-requested-length",
        title="A two-sentence question gets a short answer, not a tutorial",
        says=(
            Say(
                "In two sentences: why would a Kafka consumer group keep rebalancing?",
                (
                    Answers(),
                    Judged(
                        "The answer explains likely causes of repeated consumer-group "
                        "rebalances in about two sentences, without a long tutorial."
                    ),
                ),
            ),
        ),
    ),
    Case(
        id="relevance-follow-up-stays-in-context",
        title="A follow-up is answered in the terms of the previous answer",
        says=(
            Say("Explain the CAP theorem in three bullet points.", (Answers(),)),
            Say(
                "Which of those does a PostgreSQL primary with asynchronous replicas give up "
                "during a network partition?",
                (
                    Answers(),
                    Judged(
                        "The answer applies the CAP properties from the previous answer to "
                        "asynchronous replication during a partition (consistency of reads "
                        "from replicas versus availability), rather than restating the theorem."
                    ),
                ),
            ),
        ),
    ),
    Case(
        id="relevance-no-invented-metrics",
        title="A metric the agent has no source for is not invented",
        says=(
            Say(
                "What was our checkout conversion rate yesterday?",
                (
                    Judged(
                        "The assistant does not state a conversion rate it did not retrieve "
                        "with a tool. It either retrieves real data or explains that it has no "
                        "source for that metric and says what it would need."
                    ),
                ),
                auto_approve=True,
            ),
        ),
    ),
    Case(
        id="relevance-no-invented-confluence-page",
        title="Without Confluence access, a page summary is not made up",
        unless=("confluence",),
        says=(
            Say(
                "Summarise the Confluence page 'Payment gateway runbook' for me.",
                (
                    Judged(
                        "The assistant says it cannot access Confluence and does not invent "
                        "the content of the page."
                    ),
                ),
            ),
        ),
    ),
    Case(
        id="relevance-exact-format-only",
        title="When only a value is asked for, only the value comes back",
        says=(
            Say(
                "Give me just the cron expression for 'every weekday at 06:30', nothing else.",
                (
                    Answers(),
                    Matches(r"30\s+6\s+\*\s+\*\s+(1-5|mon-fri)"),
                    Judged("The reply is essentially only the cron expression."),
                ),
            ),
        ),
    ),
)
