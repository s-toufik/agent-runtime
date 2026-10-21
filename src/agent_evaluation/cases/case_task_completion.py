from agent_evaluation.cases.dsl import (
    Answers,
    Case,
    Contains,
    ContainsAny,
    Judged,
    Kind,
    Matches,
    Say,
    UsesAll,
    UsesAny,
)
from agent_evaluation.cases.fixtures import INCIDENTS, INCIDENTS_FILE, REGIONS, REGIONS_FILE

KIND: Kind = Kind.TASK_COMPLETION

CASES: tuple[Case, ...] = (
    Case(
        id="task-incident-analysis",
        title="Incident export analysed end to end, with the numbers right and the table saved",
        says=(
            INCIDENTS,
            Say(
                f"Analyse {INCIDENTS_FILE}: which service had the most incidents, and what is "
                "the mean time to resolve per severity? Save the per-severity table to "
                "eval_{run_id}_mttr.csv.",
                (
                    Answers(),
                    Contains("payments-api", "eval_{run_id}_mttr.csv"),
                    Matches(r"\b13[12](\.\d+)?\b"),
                    Matches(r"\b50(\.0+)?\b"),
                    Matches(r"\b12\.5\b"),
                ),
                auto_approve=True,
            ),
        ),
    ),
    Case(
        id="task-meeting-actions-round-trip",
        title="Action items are saved, then read back correctly from the file",
        says=(
            Say(
                "Save these meeting action items to eval_{run_id}_actions.md as a checklist: "
                "(1) Alice updates the payment retry policy by Friday, (2) Bob reviews pull "
                "request #482 by Wednesday, (3) Carol schedules the disaster-recovery test "
                "before the November 14 freeze.",
                (Answers(), UsesAny("files_write", "python")),
                auto_approve=True,
            ),
            Say(
                "Read eval_{run_id}_actions.md back: who owns the disaster-recovery test, and "
                "when is Alice's item due?",
                (Answers(), UsesAny("files_read", "python"), Contains("Carol", "Friday")),
                auto_approve=True,
            ),
        ),
    ),
    Case(
        id="task-postmortem-draft",
        title="A blameless post-mortem is drafted to a file with the requested sections",
        says=(
            Say(
                "Draft a blameless post-mortem for this morning's 40-minute checkout outage, "
                "caused by an expired TLS certificate on the payment gateway, and save it to "
                "eval_{run_id}_postmortem.md with the sections Summary, Impact, Timeline, Root "
                "cause and Action items.",
                (
                    Answers(),
                    UsesAny("files_write", "python"),
                    Contains("eval_{run_id}_postmortem.md"),
                ),
                auto_approve=True,
            ),
            Say(
                "Read eval_{run_id}_postmortem.md back and list its section headings.",
                (Answers(), Contains("Impact", "Timeline", "Root cause", "Action items")),
                auto_approve=True,
            ),
        ),
    ),
    Case(
        id="task-quarterly-growth-report",
        title="Quarter-over-quarter growth is computed and written as a markdown report",
        says=(
            REGIONS,
            Say(
                f"Using {REGIONS_FILE}, compute the quarter-over-quarter growth per region, "
                "write a short markdown report with a table and one paragraph of commentary to "
                "eval_{run_id}_qoq.md, and tell me which region shrank.",
                (
                    Answers(),
                    Contains("North America", "eval_{run_id}_qoq.md"),
                    Matches(r"\b30(\.0+)?\s?%"),
                    Matches(r"-?\s?4\.9\d*\s?%"),
                ),
                auto_approve=True,
            ),
        ),
    ),
    Case(
        id="task-service-database-overview",
        title="An overview of the service database is built from the real schema",
        says=(
            Say(
                "Give me an overview of the service database: each table with its row count, "
                "and the columns that look like personal or payment data.",
                (
                    Answers(),
                    UsesAny("service_db", "python"),
                    Judged(
                        "The overview lists tables with row counts and flags personal or "
                        "payment columns, all taken from the database; or it states clearly "
                        "that the database is empty. It does not invent tables or columns."
                    ),
                ),
                auto_approve=True,
            ),
        ),
    ),
    Case(
        id="task-release-notes-from-jira",
        title="Release notes are drafted from the Jira issues of a fix version",
        requires=("jira",),
        says=(
            Say(
                "Draft release notes for PAY release 4.19 from the Jira issues in that fix "
                "version, grouped into Features, Bug fixes and Known issues, with the issue "
                "keys.",
                (
                    Answers(),
                    UsesAny("jira"),
                    Judged(
                        "The release notes are grouped into Features, Bug fixes and Known "
                        "issues, cite Jira issue keys, and only mention issues the assistant "
                        "retrieved."
                    ),
                ),
                auto_approve=True,
            ),
        ),
    ),
    Case(
        id="task-pull-request-risk-review",
        title="The newest pull request is reviewed for payment-processing risk",
        requires=("bitbucket",),
        says=(
            Say(
                "Review the most recently opened pull request in payments-api and list the "
                "changes that could affect payment processing, with the file names.",
                (
                    Answers(),
                    UsesAny("bitbucket"),
                    Judged(
                        "The review names the pull request, cites specific files and explains "
                        "concretely how each listed change could affect payment processing."
                    ),
                ),
                auto_approve=True,
            ),
        ),
    ),
    Case(
        id="task-billing-reconciliation",
        title="Invoices in Oracle are reconciled with payments in the service database",
        requires=("oracle", "service_db"),
        says=(
            Say(
                "Reconcile last month's invoice count in the Oracle billing schema with the "
                "number of payments recorded in the service database, and explain any gap.",
                (
                    Answers(),
                    UsesAny("oracle", "sql"),
                    Judged(
                        "The answer gives both counts, the difference between them, and "
                        "plausible explanations for the gap grounded in the data retrieved."
                    ),
                ),
                auto_approve=True,
            ),
        ),
    ),
    Case(
        id="task-publish-a-confluence-checklist",
        title="A checklist page is published to Confluence (writes to Confluence)",
        requires=("confluence_write",),
        says=(
            Say(
                "Create a Confluence page in the ENG space titled 'Gateway certificate "
                "rotation checklist (eval {run_id})' with a 6-step checklist for rotating the "
                "payment gateway TLS certificate, and give me its link.",
                (Answers(), UsesAny("confluence_write"), ContainsAny("http", "page")),
                auto_approve=True,
            ),
        ),
    ),
    Case(
        id="task-file-a-jira-bug-from-an-incident",
        title="A Jira bug is filed from an incident analysis (writes to Jira)",
        requires=("jira_write",),
        says=(
            INCIDENTS,
            Say(
                f"Find the longest-running SEV1 incident in {INCIDENTS_FILE} and file a Jira "
                "bug for its root cause in the PAY project, labelled eval-{run_id}. Give me the "
                "issue key.",
                (
                    Answers(),
                    UsesAll("python", "jira_write"),
                    Matches(r"\b[A-Z][A-Z0-9]+-\d+\b"),
                    Contains("disk full"),
                ),
                auto_approve=True,
            ),
        ),
    ),
)
