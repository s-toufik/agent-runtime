import argparse
import asyncio
import logging
import sys
from pathlib import Path

from pydantic import ValidationError

from agent_evaluation.application.evaluation_plan import EvaluationPlan
from agent_evaluation.bootstrap.container import ConfigurationError, EvaluationContainer
from agent_evaluation.cases import CATALOG
from agent_evaluation.configuration.control_panel import ControlPanel
from agent_evaluation.configuration.overrides import Overrides
from agent_evaluation.domain.exception import AgentUnavailable
from agent_evaluation.domain.kind import Kind
from agent_evaluation.domain.result import Status

DEFAULT_PANEL: Path = Path(__file__).resolve().parents[1] / "control_panel.json"
ROOT_LOGGER: str = "agent_evaluation"
CONSOLE: str = "_evaluation_console"

logger: logging.Logger = logging.getLogger(ROOT_LOGGER)

OK, FAILED, UNUSABLE, INTERRUPTED = 0, 1, 2, 130


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        overrides = _overrides(arguments)
        panel = overrides.apply(ControlPanel.load(Path(arguments.panel)))
    except (OSError, ValueError, ValidationError) as error:
        print(f"Control panel {arguments.panel} is not usable:\n{error}", file=sys.stderr)
        return UNUSABLE

    _console(panel.run.console_log_level)
    container = EvaluationContainer(panel, Path(arguments.panel), overrides, CATALOG)
    try:
        container.validate()
    except ConfigurationError as error:
        logger.error(f"Invalid evaluation setup: {error}")
        return UNUSABLE

    suites = container.suites()
    if not suites:
        logger.error("Nothing to run: no kind is enabled or no case matches --cases")
        return UNUSABLE
    for line in EvaluationPlan(suites, container.rules.capabilities).describe():
        logger.info(line)
    if arguments.dry_run:
        return OK

    try:
        outcome = asyncio.run(container.run(suites))
    except AgentUnavailable as error:
        logger.error(f"The agent is not usable: {error}")
        return UNUSABLE
    except KeyboardInterrupt:
        logger.warning("Interrupted: reports were written for the kinds that finished")
        return INTERRUPTED
    finished = (Status.PASSED, Status.SKIPPED)
    return OK if all(result.status in finished for result in outcome.results) else FAILED


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent_evaluation",
        description="Evaluate a running agent over HTTP, driven by a JSON control panel.",
    )
    parser.add_argument("--panel", default=str(DEFAULT_PANEL), help="control panel JSON file")
    parser.add_argument("--kinds", help=f"comma-separated kinds: {', '.join(Kind)}")
    parser.add_argument("--cases", help="comma-separated case id patterns, e.g. 'memory-*'")
    parser.add_argument("--runs", type=int, help="runs per case, forced for every case")
    parser.add_argument("--pause", type=float, help="seconds between runs, forced for every case")
    parser.add_argument("--agent-url", help="agent base URL, e.g. http://localhost:8001")
    parser.add_argument("--endpoint", help="agent streaming endpoint, e.g. /v1/stream")
    parser.add_argument("--model", help="model_name sent to the agent")
    parser.add_argument("--output-dir", help="directory for the reports")
    parser.add_argument("--dry-run", action="store_true", help="show what would run and stop")
    return parser


def _overrides(arguments: argparse.Namespace) -> Overrides:
    return Overrides(
        kinds=tuple(Kind(item.strip().upper()) for item in _items(arguments.kinds)),
        cases=_items(arguments.cases),
        runs=arguments.runs,
        pause_between_runs_seconds=arguments.pause,
        agent_url=arguments.agent_url,
        endpoint=arguments.endpoint,
        model_name=arguments.model,
        output_dir=arguments.output_dir,
    )


def _items(text: str | None) -> tuple[str, ...]:
    return tuple(item.strip() for item in (text or "").split(",") if item.strip())


def _console(level: str) -> None:
    for handler in [h for h in logger.handlers if getattr(h, CONSOLE, False)]:
        logger.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    setattr(handler, CONSOLE, True)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
