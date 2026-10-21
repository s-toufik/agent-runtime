from agent_evaluation.cases.dsl import (
    Answers,
    Case,
    Contains,
    Judged,
    Kind,
    Matches,
    NotContains,
    Say,
    UsesAny,
    UsesNoTools,
)
from agent_evaluation.cases.fixtures import INCIDENTS, INCIDENTS_FILE

KIND: Kind = Kind.MEMORY

DETOURS: tuple[str, ...] = (
    "In two sentences: what is a deadlock in PostgreSQL and how do I spot one?",
    "In one sentence: what does an idempotency key protect against in a payment API?",
    "Give me a cron expression for every weekday at 06:30, nothing else.",
    "In two sentences: when should I prefer a message queue over a synchronous HTTP call?",
    "In one sentence: what is the difference between RPO and RTO?",
    "In two sentences: why can a retry storm make an outage worse?",
)

CASES: tuple[Case, ...] = (
    Case(
        id="memory-facts-after-a-detour",
        title="Facts given at the start are recalled after an unrelated question",
        says=(
            Say(
                "Context for this conversation: the production database is ora-prod-07, the "
                "on-call engineer this week is Priya Raman, and the change freeze starts on "
                "November 14.",
                (Answers(), UsesNoTools()),
            ),
            Say(
                "Unrelated: in two sentences, how do I spot a deadlock in PostgreSQL?",
                (Answers(),),
            ),
            Say(
                "Who is on call this week, which database is production, and when does the "
                "freeze start?",
                (Answers(), Contains("Priya", "ora-prod-07"), Matches(r"\b14\b")),
            ),
        ),
    ),
    Case(
        id="memory-that-file",
        title="'That file' is resolved to the file written earlier in the conversation",
        says=(
            Say(
                "Write a three-line Q3 summary to eval_{run_id}_q3.md: revenue grew 12 %, churn "
                "fell to 2.1 %, NPS is 48.",
                (Answers(), UsesAny("files_write", "python")),
                auto_approve=True,
            ),
            Say(
                "Now read that file back and tell me the churn figure.",
                (Answers(), UsesAny("files_read", "python"), Contains("2.1")),
                auto_approve=True,
            ),
        ),
    ),
    Case(
        id="memory-language-preference",
        title="A language preference set once holds for the next questions",
        says=(
            Say("From now on, please answer in French and keep it short.", (Answers(),)),
            Say("What is a primary key in a relational database?", (Answers(),)),
            Say(
                "And what is a foreign key?",
                (Answers(), Judged("The last answer is written in French.")),
            ),
        ),
    ),
    Case(
        id="memory-correction-wins",
        title="A correction replaces the earlier fact",
        says=(
            Say("Our SLA for SEV1 incidents is 4 hours.", (Answers(),)),
            Say("Correction: the SEV1 SLA is 2 hours, not 4.", (Answers(),)),
            Say(
                "A SEV1 was opened at 09:00. By what time must it be resolved to meet our SLA?",
                (Answers(), Contains("11:00"), NotContains("13:00")),
            ),
        ),
    ),
    Case(
        id="memory-long-conversation",
        title="A fact from the first message survives a long conversation",
        says=(
            Say(
                "Note for later: the ledger migration project is code-named Halcyon and its "
                "budget is 240k EUR.",
                (Answers(),),
            ),
            *(Say(question, (Answers(),)) for question in DETOURS),
            Say(
                "What was the project code name and budget I gave you at the start?",
                (Answers(), Contains("Halcyon", "240")),
            ),
        ),
    ),
    Case(
        id="memory-no-leak-between-conversations",
        title="Something said in one conversation is not known in another",
        says=(
            Say(
                "Remember this for later: the vendor escrow code is ZEPHYR-{run_id}.",
                (Answers(),),
                conversation="first",
            ),
            Say(
                "What vendor escrow code did I give you earlier?",
                (
                    NotContains("ZEPHYR-{run_id}"),
                    Judged(
                        "The assistant says it has no record of an escrow code in this "
                        "conversation, and does not invent one."
                    ),
                ),
                conversation="second",
            ),
        ),
    ),
    Case(
        id="memory-earlier-result",
        title="A follow-up builds on the result of the previous answer",
        says=(
            INCIDENTS,
            Say(
                f"Which service had the most incidents in {INCIDENTS_FILE}?",
                (Answers(), Contains("payments-api")),
                auto_approve=True,
            ),
            Say(
                "And how many incidents did that service have, and how many minutes did they "
                "take to resolve in total?",
                (Answers(), Matches(r"\b(4|four)\b"), Matches(r"\b200\b")),
                auto_approve=True,
            ),
        ),
    ),
)
