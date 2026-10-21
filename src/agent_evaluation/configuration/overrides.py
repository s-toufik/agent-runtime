from dataclasses import dataclass

from agent_evaluation.configuration.control_panel import ControlPanel
from agent_evaluation.domain.kind import Kind


@dataclass(frozen=True, slots=True)
class Overrides:
    kinds: tuple[Kind, ...] = ()
    cases: tuple[str, ...] = ()
    runs: int | None = None
    pause_between_runs_seconds: float | None = None
    agent_url: str | None = None
    endpoint: str | None = None
    model_name: str | None = None
    output_dir: str | None = None

    def apply(self, panel: ControlPanel) -> ControlPanel:
        agent = panel.agent.model_copy(
            update=_present(
                base_url=self.agent_url, endpoint=self.endpoint, model_name=self.model_name
            )
        )
        run = panel.run.model_copy(update=_present(output_dir=self.output_dir))
        return panel.model_copy(update={"agent": agent, "run": run})


def _present(**values: object) -> dict[str, object]:
    return {key: value for key, value in values.items() if value is not None}
