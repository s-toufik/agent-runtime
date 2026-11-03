import logging
import os
from collections import Counter
from collections.abc import Mapping
from fnmatch import fnmatchcase
from pathlib import Path

import httpx
from dotenv import dotenv_values

from agent_evaluation.adapter.agent.http_agent import HttpAgent
from agent_evaluation.adapter.clock.system_clock import SystemClock
from agent_evaluation.adapter.journal.file_journal import FileJournal
from agent_evaluation.adapter.judge.langchain_judge import LangChainJudge
from agent_evaluation.adapter.report.file_report_writer import FileReportWriter
from agent_evaluation.adapter.report.report_header import ReportHeader
from agent_evaluation.adapter.report.report_paths import ReportPaths
from agent_evaluation.application.case_player import CasePlayer
from agent_evaluation.application.evaluation import Evaluation, EvaluationOutcome
from agent_evaluation.application.kind_evaluator import KindEvaluator
from agent_evaluation.application.kind_suite import KindSuite
from agent_evaluation.application.paced_judge import PacedJudge
from agent_evaluation.configuration.control_panel import ControlPanel
from agent_evaluation.configuration.overrides import Overrides
from agent_evaluation.domain.capability import Capabilities, Capability
from agent_evaluation.domain.case import Case
from agent_evaluation.domain.kind import Kind
from agent_evaluation.domain.rules import Markers, Rules, SecurityRules
from agent_evaluation.domain.run_policy import RunPolicy

logger: logging.Logger = logging.getLogger(__name__)

NO_KEY: str = "no-key"


class ConfigurationError(Exception):
    pass


class EvaluationContainer:
    def __init__(
        self,
        panel: ControlPanel,
        panel_path: Path,
        overrides: Overrides,
        catalog: Mapping[Kind, tuple[Case, ...]],
    ) -> None:
        self._panel = panel
        self._panel_path = panel_path
        self._overrides = overrides
        self._catalog = catalog
        self._clock = SystemClock()
        self.rules: Rules = Rules(
            capabilities=Capabilities(
                Capability(name, section.available, tuple(section.tools))
                for name, section in panel.capabilities.items()
            ),
            markers=Markers(panel.markers.plan_status, panel.markers.tool_status_prefix),
            security=SecurityRules(
                tuple(panel.security.instruction_markers), tuple(panel.security.secret_patterns)
            ),
            pass_score=panel.judge.pass_score,
        )

    def validate(self) -> None:
        cases = [case for cases in self._catalog.values() for case in cases]
        problems: list[str] = []
        duplicates = [
            name for name, count in Counter(case.id for case in cases).items() if count > 1
        ]
        if duplicates:
            problems.append(f"duplicate case ids: {', '.join(sorted(duplicates))}")
        unknown = sorted(
            {name for case in cases for name in self.rules.capabilities.unknown(case.capabilities)}
        )
        if unknown:
            problems.append(
                f"capabilities used by cases but missing from the panel: {', '.join(unknown)}"
            )
        ids = {case.id for case in cases}
        for kind, section in self._panel.kinds.items():
            stray = [case_id for case_id in section.skip_cases if case_id not in ids]
            if stray:
                problems.append(f"kinds.{kind}.skip_cases names unknown cases: {', '.join(stray)}")
        if problems:
            raise ConfigurationError("; ".join(problems))

    def suites(self) -> tuple[KindSuite, ...]:
        run = self._panel.run
        kinds = self._overrides.kinds or tuple(
            kind for kind in Kind if self._panel.kind(kind).enabled
        )
        suites: list[KindSuite] = []
        for kind in kinds:
            section = self._panel.kind(kind)
            cases = tuple(case for case in self._catalog.get(kind, ()) if self._selected(case))
            if self._overrides.cases and not cases:
                continue
            policy = RunPolicy(
                runs=section.runs or run.runs,
                pause_between_runs_seconds=_first(
                    section.pause_between_runs_seconds, run.pause_between_runs_seconds
                ),
                pause_between_messages_seconds=run.pause_between_messages_seconds,
                pause_between_cases_seconds=_first(
                    section.pause_between_cases_seconds, run.pause_between_cases_seconds
                ),
                retry_on_error=run.retry_on_error,
                retry_pause_seconds=run.retry_pause_seconds,
                case_pass_rate=run.case_pass_rate,
                forced_runs=self._overrides.runs,
                forced_pause_between_runs_seconds=self._overrides.pause_between_runs_seconds,
            )
            suites.append(KindSuite(kind, cases, policy, frozenset(section.skip_cases)))
        return tuple(suites)

    async def run(self, suites: tuple[KindSuite, ...]) -> EvaluationOutcome:
        agent_panel = self._panel.agent
        started_at = self._clock.now()
        paths = ReportPaths(Path(self._panel.run.output_dir), started_at)
        async with httpx.AsyncClient() as client:
            agent = HttpAgent(
                client,
                agent_panel.base_url,
                agent_panel.endpoint,
                agent_panel.models_endpoint,
                agent_panel.model_name,
                agent_panel.timeout_seconds,
                agent_panel.headers,
            )
            judge = PacedJudge(
                self._judge(), self._clock, self._panel.judge.pause_between_calls_seconds
            )
            header = ReportHeader(
                started_at=started_at,
                agent_url=agent.url,
                model_name=agent_panel.model_name,
                judge_model=self._panel.judge.model_name,
                pass_score=self._panel.judge.pass_score,
                panel=str(self._panel_path),
            )
            evaluation = Evaluation(
                agent,
                KindEvaluator(
                    CasePlayer(agent, judge, self._clock, self.rules), self._clock, self.rules
                ),
                FileReportWriter(paths, header),
                FileJournal(paths),
                self._clock,
            )
            return await evaluation.run(suites)

    def _judge(self) -> LangChainJudge:
        judge = self._panel.judge
        return LangChainJudge.from_settings(
            base_url=judge.base_url,
            api_key=self._judge_key(),
            model_name=judge.model_name,
            temperature=judge.temperature,
            max_output_tokens=judge.max_output_tokens,
            max_context_tokens=judge.max_context_tokens,
            timeout_seconds=judge.timeout_seconds,
            reasoning_effort=judge.reasoning_effort,
        )

    def _judge_key(self) -> str:
        judge = self._panel.judge
        if not judge.api_key_env:
            return NO_KEY
        key = os.environ.get(judge.api_key_env)
        if not key and judge.env_file and Path(judge.env_file).is_file():
            key = dotenv_values(judge.env_file).get(judge.api_key_env)
        if not key:
            logger.warning(
                f"No judge API key: {judge.api_key_env} is not set in the environment "
                f"or in {judge.env_file}; the judge is called without one"
            )
        return key or NO_KEY

    def _selected(self, case: Case) -> bool:
        patterns = self._overrides.cases
        return not patterns or any(fnmatchcase(case.id, pattern) for pattern in patterns)


def _first(value: float | None, default: float) -> float:
    return default if value is None else value
