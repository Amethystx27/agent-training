"""Load experiment configuration without copying or exposing secrets."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from openai import OpenAI


EXPERIMENT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ENV_PATH = EXPERIMENT_DIR.parent / ".env"


class ConfigurationError(ValueError):
    """Raised when the experiment environment is incomplete or invalid."""


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Validated application configuration.

    The API key is excluded from repr so configuration objects can be logged
    safely. Never print the key itself.
    """

    api_key: str = field(repr=False)
    base_url: str
    model_name: str
    request_timeout: float = 30.0

    def create_openai_client(self) -> OpenAI:
        """Create an OpenAI-compatible client using the validated settings."""

        return OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.request_timeout,
        )


def _read_required_value(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigurationError(
            f"Required environment variable {name} is missing or empty."
        )
    return value


def _validate_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ConfigurationError(
            "OPENAI_BASE_URL must be an absolute HTTP(S) URL."
        )
    if parsed.username or parsed.password:
        raise ConfigurationError(
            "OPENAI_BASE_URL must not contain credentials."
        )
    return base_url.rstrip("/")


def load_config(env_path: Path | str | None = None) -> AppConfig:
    """Load and validate settings from the parent directory's .env file.

    Existing process environment variables take precedence. The default path
    deliberately points to the parent folder so the secret file does not need
    to be copied into the experiment directory.
    """

    resolved_env_path = Path(env_path).expanduser().resolve() if env_path else DEFAULT_ENV_PATH
    if not resolved_env_path.is_file():
        raise ConfigurationError(
            f"Environment file not found: {resolved_env_path}"
        )

    load_dotenv(dotenv_path=resolved_env_path, override=False)

    return AppConfig(
        api_key=_read_required_value("OPENAI_API_KEY"),
        base_url=_validate_base_url(_read_required_value("OPENAI_BASE_URL")),
        model_name=_read_required_value("MODEL_NAME"),
    )
