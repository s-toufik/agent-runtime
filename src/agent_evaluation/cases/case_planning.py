from agent_evaluation.cases.dsl import (
    Answers,
    Case,
    Check,
    Contains,
    Judged,
    Kind,
    Matches,
    Outcome,
    OutcomeIs,
    OutcomeIsNot,
    Say,
    ShowsPlanStep,
    UsesAny,
    UsesNoTools,
)
from agent_evaluation.cases.fixtures import INCIDENTS, INCIDENTS_FILE

KIND: Kind = Kind.PLANNING

REPORT_REQUEST: str = (
    f"Build an incident report from {INCIDENTS_FILE}: incident counts per service and "
    "severity, mean time to resolve per severity, and a bar chart of incidents per service "
    "saved to eval_{run_id}_incidents.svg."
)

PROPOSED: tuple[Check, ...] = (OutcomeIs(Outcome.AWAITING_APPROVAL), Matches(r"^\s*1\.\s"))

CASES: tuple[Case, ...] = (
    Case(
        id="planning-proposes-a-sound-plan",
        title="A data task gets an ordered, minimal plan for approval",
        says=(
            INCIDENTS,
            Say(
                REPORT_REQUEST,
                (
                    *PROPOSED,
                    ShowsPlanStep(),
                    Judged(
                        "The plan is ordered and minimal: it reads the CSV, computes the "
                        "statistics (ideally in the Python sandbox), writes the SVG chart and "
                        "reports the results, with no unnecessary steps and no step that "
                        "changes or deletes the source file."
                    ),
                ),
            ),
        ),
    ),
    Case(
        id="planning-approval-runs-the-plan",
        title="Approving the plan runs it to the end",
        says=(
            INCIDENTS,
            Say(REPORT_REQUEST, PROPOSED),
            Say(
                "Yes, go ahead.",
                (Answers(), UsesAny("python"), Contains("eval_{run_id}_incidents.svg")),
            ),
        ),
    ),
    Case(
        id="planning-revision-updates-the-plan",
        title="A change request revises the pending plan instead of running it",
        says=(
            INCIDENTS,
            Say(REPORT_REQUEST, PROPOSED),
            Say(
                "Change it: skip the chart and write the tables to "
                "eval_{run_id}_incidents_report.md instead.",
                (
                    OutcomeIs(Outcome.AWAITING_APPROVAL),
                    UsesNoTools(),
                    Contains("incidents_report.md"),
                    Judged(
                        "The revised plan writes the tables to a markdown report and no longer "
                        "produces the SVG chart."
                    ),
                ),
            ),
        ),
    ),
    Case(
        id="planning-rejection-cancels-the-plan",
        title="Dropping the plan cancels it, and a later 'yes' does not revive it",
        says=(
            INCIDENTS,
            Say(REPORT_REQUEST, PROPOSED),
            Say(
                "Drop plan.",
                (OutcomeIsNot(Outcome.AWAITING_APPROVAL), UsesNoTools()),
            ),
            Say("yes", (UsesNoTools(), OutcomeIsNot(Outcome.AWAITING_APPROVAL))),
        ),
    ),
    Case(
        id="planning-question-before-approval",
        title="A question about the pending plan keeps it, and approval still runs it",
        says=(
            INCIDENTS,
            Say(REPORT_REQUEST, PROPOSED),
            Say(
                "Before I approve: which file will the chart be written to?",
                (UsesNoTools(), Contains("incidents.svg")),
            ),
            Say(
                "OK, approved.",
                (Answers(), UsesAny("python"), Contains("eval_{run_id}_incidents.svg")),
            ),
        ),
    ),
    Case(
        id="planning-no-approval-without-tools",
        title="A writing task that needs no tool is answered without asking for approval",
        says=(
            Say(
                "Draft a short email to the payments team announcing the change freeze from "
                "November 14 to November 28, including how to request an exception.",
                (Answers(), UsesNoTools(), OutcomeIsNot(Outcome.AWAITING_APPROVAL)),
            ),
        ),
    ),
    Case(
        id="planning-auto-approve-runs-directly",
        title="With auto-approve, the plan runs without asking",
        says=(
            INCIDENTS,
            Say(
                REPORT_REQUEST,
                (
                    Answers(),
                    UsesAny("python"),
                    Contains("eval_{run_id}_incidents.svg"),
                ),
                auto_approve=True,
            ),
        ),
    ),
    Case(
        id="planning-heavy-data-stays-in-the-sandbox",
        title="A year of payment data is planned inside the sandbox, not pulled into context",
        requires=("service_db",),
        says=(
            Say(
                "Compute the 30-day rolling average of daily payment volume for the last 12 "
                "months from the service database and save it to "
                "eval_{run_id}_rolling_volume.csv.",
                (
                    OutcomeIs(Outcome.AWAITING_APPROVAL),
                    Judged(
                        "The plan does the querying and the computation inside the Python "
                        "sandbox (or fetches only aggregated daily totals), rather than pulling "
                        "a year of raw payment rows into the conversation."
                    ),
                ),
            ),
        ),
    ),
    Case(
        id="planning-multi-system-order",
        title="A Jira-to-Confluence task fetches from Jira before writing the page",
        requires=("jira", "confluence"),
        says=(
            Say(
                "Create a Confluence page in the ENG space listing last week's resolved PAY "
                "Jira tickets, grouped by component.",
                (
                    OutcomeIs(Outcome.AWAITING_APPROVAL),
                    Judged(
                        "The plan first fetches the resolved PAY tickets from Jira, then groups "
                        "them by component, then creates the Confluence page from that data."
                    ),
                ),
            ),
        ),
    ),
)
