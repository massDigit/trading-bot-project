"""Configuration loading for the IG demo diagnostic.

The base URL is deliberately NOT configurable: this first version is locked on
the IG demo environment. Secrets are read from the local `.env.demo` file (or the
process environment) and never from the command line. A future live
configuration will use its own file and is never loaded by this version.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

# Locked target. Do not make this configurable in V1 (cahier des charges §11).
IG_DEMO_BASE_URL = "https://demo-api.ig.com/gateway/deal"

REQUIRED_VARS = ("IG_API_KEY", "IG_USERNAME", "IG_PASSWORD")
# Variables that would suggest an attempt to target another environment.
FORBIDDEN_VARS = ("IG_BASE_URL", "IG_API_URL", "IG_ENVIRONMENT", "IG_ACC_TYPE")

DEFAULT_SEARCH_TERM = "EUR/USD"

# Demo secrets file, one file per environment (cahier des charges §11).
DEMO_ENV_FILE = ".env.demo"


class ConfigError(Exception):
    """Raised when the local configuration is missing or unsafe."""


@dataclass(frozen=True, repr=False)
class Settings:
    api_key: str
    username: str
    password: str
    account_id: str | None
    search_term: str
    base_url: str = IG_DEMO_BASE_URL

    def __repr__(self) -> str:  # never leak secrets through repr()
        return "Settings(<masqué>)"

    def secrets(self) -> dict[str, str]:
        """Values that must never appear in any output."""
        values = {
            "IG_API_KEY": self.api_key,
            "IG_USERNAME": self.username,
            "IG_PASSWORD": self.password,
        }
        if self.account_id:
            values["IG_ACCOUNT_ID"] = self.account_id
        return values


def load_settings(env_file: Path | None = None) -> Settings:
    """Load settings from `.env.demo` (if present), overridden by the process environment."""
    file_values: dict[str, str | None] = {}
    path = env_file if env_file is not None else Path.cwd() / DEMO_ENV_FILE
    if path.is_file():
        file_values = dict(dotenv_values(path))

    def get(name: str) -> str:
        value = os.environ.get(name)
        if value is None:
            value = file_values.get(name) or ""
        return value.strip()

    present_forbidden = [name for name in FORBIDDEN_VARS if get(name)]
    if present_forbidden:
        raise ConfigError(
            "Variables non autorisées en V1 (environnement verrouillé sur la démo) : " + ", ".join(present_forbidden)
        )

    missing = [name for name in REQUIRED_VARS if not get(name)]
    if missing:
        raise ConfigError(
            "Variables manquantes : "
            + ", ".join(missing)
            + f". Copier .env.example en {DEMO_ENV_FILE} et les renseigner localement."
        )

    return Settings(
        api_key=get("IG_API_KEY"),
        username=get("IG_USERNAME"),
        password=get("IG_PASSWORD"),
        account_id=get("IG_ACCOUNT_ID") or None,
        search_term=get("IG_MARKET_SEARCH_TERM") or DEFAULT_SEARCH_TERM,
    )
