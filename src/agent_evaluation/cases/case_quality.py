from agent_evaluation.cases.dsl import (
    Answers,
    Case,
    Contains,
    Judged,
    Kind,
    Matches,
    Say,
)
from agent_evaluation.cases.fixtures import REGIONS, REGIONS_FILE

KIND: Kind = Kind.QUALITY

PAYMENT_HANDLER: str = """\
```python
def charge(user_id, amount):
    total = float(amount) * 1.2
    try:
        gateway.charge(user_id, total)
    except Exception:
        gateway.charge(user_id, total)
    db.execute(f"UPDATE balances SET paid = paid + {total} WHERE user_id = {user_id}")
```"""

CASES: tuple[Case, ...] = (
    Case(
        id="quality-zero-downtime-migration",
        title="Advice for a large online schema change is correct and actionable",
        says=(
            Say(
                "We need to add a NOT NULL column with a default to a 200-million-row payments "
                "table in PostgreSQL 16 without downtime. How should we roll it out?",
                (
                    Answers(),
                    Judged(
                        "The advice is technically correct for PostgreSQL 16 and actionable: "
                        "it avoids long table locks (e.g. add the column nullable or rely on "
                        "the fast default, backfill in batches, add the constraint with NOT "
                        "VALID then VALIDATE or equivalent), mentions lock timeouts and a "
                        "rollback path, and is structured as steps."
                    ),
                ),
            ),
        ),
    ),
    Case(
        id="quality-broker-comparison-table",
        title="A comparison asked as a table is an accurate markdown table",
        says=(
            Say(
                "Compare Kafka, RabbitMQ and Amazon SQS for an order-events pipeline: "
                "ordering, delivery guarantees, replay and operational cost. Answer as a "
                "markdown table.",
                (
                    Answers(),
                    Matches(r"^\|.+\|\s*$"),
                    Matches(r"^\|?\s*:?-{3,}"),
                    Judged(
                        "The table is accurate: e.g. Kafka orders per partition and supports "
                        "replay, SQS FIFO orders per message group and standard queues do not "
                        "guarantee order, RabbitMQ has no native replay of consumed messages; "
                        "all four criteria are covered for all three systems."
                    ),
                ),
            ),
        ),
    ),
    Case(
        id="quality-retry-helper-code",
        title="Requested code is correct, typed and does what was asked",
        says=(
            Say(
                "Write a Python async function that calls an HTTP endpoint with httpx and "
                "retries on 429 and 5xx responses with exponential backoff and full jitter, at "
                "most 5 attempts, with type hints.",
                (
                    Answers(),
                    Contains("async def", "httpx"),
                    Judged(
                        "The code is correct: it retries only on 429 and 5xx (and possibly "
                        "transport errors), uses exponential backoff with full jitter, stops "
                        "after 5 attempts and then raises or returns the last response, uses "
                        "async httpx properly and has type hints."
                    ),
                ),
            ),
        ),
    ),
    Case(
        id="quality-top-customers-sql",
        title="A SQL query written from a schema is correct",
        says=(
            Say(
                "Write a SQL query that returns the top 5 customers by total payment amount "
                "over the last 90 days. Tables: customers(id, name), payments(id, customer_id, "
                "amount, paid_at).",
                (
                    Answers(),
                    Matches(r"group\s+by"),
                    Matches(r"limit\s+5|fetch\s+first\s+5"),
                    Judged(
                        "The query joins payments to customers, filters paid_at to the last 90 "
                        "days, sums amount per customer, orders by that total descending and "
                        "keeps 5 rows."
                    ),
                ),
            ),
        ),
    ),
    Case(
        id="quality-honest-about-the-future",
        title="A request for a future exchange rate is not answered with false certainty",
        says=(
            Say(
                "What will the EUR/USD exchange rate be on 1 March next year? I need one number "
                "for the budget.",
                (
                    Answers(),
                    Judged(
                        "The assistant does not present a precise future rate as fact. It "
                        "explains the uncertainty and gives a usable way to budget (forward "
                        "rate, a range or a conservative assumption)."
                    ),
                ),
            ),
        ),
    ),
    Case(
        id="quality-customer-status-update",
        title="A customer-facing outage update has the right tone and content",
        says=(
            Say(
                "Write a customer-facing status update for a 40-minute card-payment outage this "
                "morning caused by an expired TLS certificate; it is resolved now. Under 120 "
                "words.",
                (
                    Answers(),
                    Judged(
                        "The update is clear and apologetic, says the issue is resolved and "
                        "what is being done to prevent it happening again, avoids internal "
                        "jargon and blame, and stays under about 120 words."
                    ),
                ),
            ),
        ),
    ),
    Case(
        id="quality-executive-summary-from-data",
        title="An executive summary built from data is accurate and concise",
        says=(
            REGIONS,
            Say(
                f"Using {REGIONS_FILE}, write a four-sentence executive summary of Q3 versus Q2 "
                "revenue by region for the CFO.",
                (
                    Answers(),
                    Contains("North America"),
                    Judged(
                        "The summary is consistent with the data (APAC +30 %, EMEA +15 %, "
                        "LATAM +10 %, North America about -4.9 %, total about +8 %), is about "
                        "four sentences and reads as an executive summary."
                    ),
                ),
                auto_approve=True,
            ),
        ),
    ),
    Case(
        id="quality-code-review-priorities",
        title="A code review finds the serious problems first",
        says=(
            Say(
                "Review this payment handler and list its problems, most serious first:\n\n"
                + PAYMENT_HANDLER,
                (
                    Answers(),
                    Judged(
                        "The review identifies at least: the retry in the except block that "
                        "can charge the customer twice (no idempotency), the SQL injection in "
                        "the f-string query, and the use of float for money; and it puts the "
                        "double charge or the SQL injection near the top."
                    ),
                ),
            ),
        ),
    ),
)
