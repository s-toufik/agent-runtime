import os
from dataclasses import dataclass
from pathlib import Path

import dotenv

DEFAULT_AGENT: str = "supervisor"
DEFAULT_AGENTS_DIRECTORY: Path = Path("./agents")


@dataclass(frozen=True, slots=True)
class ProcessSettings:
    environment: str
    configuration_directory: Path
    agent: str = DEFAULT_AGENT
    agents_directory: Path = DEFAULT_AGENTS_DIRECTORY

    @property
    def service_name(self) -> str:
        return f"agent-{self.agent}"

    @classmethod
    def from_environment(cls) -> ProcessSettings:
        dotenv.load_dotenv()
        directory = os.getenv("CONFIGURATION_DIR", "./config")

        return cls(
            environment=os.getenv("APP_ENV", "debug"),
            configuration_directory=Path(directory),
            agent=os.getenv("AGENT", "").strip() or DEFAULT_AGENT,
            agents_directory=Path(os.getenv("AGENTS_DIR", "").strip() or DEFAULT_AGENTS_DIRECTORY),
        )
