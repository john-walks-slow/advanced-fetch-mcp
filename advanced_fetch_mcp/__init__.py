from __future__ import annotations

from .env_loader import load_project_dotenv

_LOADED_ENV_FILE = load_project_dotenv()

__all__ = ["mcp", "cleanup"]


def __getattr__(name: str):
    if name == "mcp":
        from .server import mcp

        return mcp
    if name == "cleanup":
        from .server import cleanup

        return cleanup
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
