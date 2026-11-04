"""Application configuration loaded from environment variables.

All settings are read at import time via :func:`Settings.from_env`.
The resulting object is immutable (frozen dataclass) to prevent accidental
mutation after startup.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Immutable application settings.

    Attributes:
        environment: Runtime environment name (e.g. ``development``, ``production``).
        log_level: Python logging level string (e.g. ``INFO``, ``DEBUG``).
        log_dir: Directory path where log files are written.
        log_json: When ``True`` structured JSON is emitted to the console handler.

    """

    environment: str
    log_level: str
    log_dir: str
    log_json: bool

    @classmethod
    def from_env(cls) -> Settings:
        """Construct :class:`Settings` from environment variables with safe defaults.

        Returns:
            A fully populated, frozen :class:`Settings` instance.

        """
        return cls(
            environment=os.getenv("ENVIRONMENT", "development"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            log_dir=os.getenv("LOG_DIR", "logs"),
            log_json=os.getenv("LOG_JSON", "false").lower() in ("1", "true", "yes"),
        )


# Module-level singleton — import and use directly.
settings: Settings = Settings.from_env()
