from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def _explicit_env_file() -> Optional[Path]:
    raw = os.getenv("ADVANCED_FETCH_ENV_FILE")
    if not raw:
        return None
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    if candidate.is_file():
        return candidate
    return None


def find_env_file(filename: str = ".env") -> Optional[Path]:
    explicit = _explicit_env_file()
    if explicit is not None:
        return explicit

    candidate = Path.cwd() / filename
    if candidate.is_file():
        return candidate
    return None


def load_project_dotenv(override: bool = False) -> Optional[Path]:
    env_file = find_env_file()
    if env_file is None:
        return None
    load_dotenv(env_file, override=override)
    return env_file
