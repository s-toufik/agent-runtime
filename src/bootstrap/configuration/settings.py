import os
from dataclasses import dataclass
from pathlib import Path

import dotenv

DEFAULT_AGENT: str = "chat"
DEFAULT_AGENTS_DIRECTORY: Path = Path("./agents")


@dataclass(frozen=True, slots=True)
class ProcessSettings:
    role: str
    environment: str
    configuration_directory: Path
    guardrail_enabled: bool = False
    agent: str = DEFAULT_AGENT
    agents_directory: Path = DEFAULT_AGENTS_DIRECTORY

    @classmethod
    def for_role(cls, role: str) -> ProcessSettings:
        dotenv.load_dotenv()
        directory = os.getenv("CONFIGURATION_DIR", "./config")

        return cls(
            role=role,
            environment=os.getenv("APP_ENV", "debug"),
            configuration_directory=Path(directory),
            guardrail_enabled=os.getenv("GUARDRAIL_ENABLED", "").strip()
            in ("true", "1", "on", "yes"),
            agent=os.getenv("AGENT", "").strip() or DEFAULT_AGENT,
            agents_directory=Path(os.getenv("AGENTS_DIR", "").strip() or DEFAULT_AGENTS_DIRECTORY),
        )
