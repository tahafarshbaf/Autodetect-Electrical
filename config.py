"""
Centralized configuration for the Vision Scan (Autodetect Electrical) app.

All machine-specific paths - YOLO model weights, company logo, PR tracking
file - are read from environment variables instead of being hardcoded in
shared.py. This lets the app run on any machine or user account without
editing source code, and keeps personal file paths out of version control.

Setup:
    1. Copy `.env.example` to `.env` in the project root.
    2. Fill in the real paths for your machine.
    3. Run the app as usual (`streamlit run app.py`). python-dotenv loads
       `.env` automatically on startup - no need to set OS-level
       environment variables manually.

If a required path is missing, ConfigError is raised immediately on
import (from app.py), with a message that says exactly which setting is
missing and how to fix it, instead of a cryptic FileNotFoundError deep
inside a library call later on.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Resolve .env relative to this file (not the current working directory),
# so the app finds it regardless of where `streamlit run` is launched from.
_PROJECT_ROOT = Path(__file__).resolve().parent
_ENV_PATH = _PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=_ENV_PATH)


class ConfigError(RuntimeError):
    """Raised when a required configuration value is missing or invalid."""


def _get_path(env_var: str, required: bool = True) -> str:
    """
    Reads a filesystem path from an environment variable.

    Args:
        env_var: name of the environment variable to read.
        required: if True and the variable is unset/blank, raises
                   ConfigError with setup instructions. If False, returns
                   an empty string instead so the caller can fall back
                   gracefully (e.g. a placeholder logo).

    Returns:
        The path as a string. Not checked for existence on disk here -
        callers decide when/how to validate that, since some paths (e.g.
        the PR file) must already exist while others may be created.
    """
    value = os.environ.get(env_var, "").strip()
    if not value and required:
        raise ConfigError(
            f"Missing required setting: {env_var}\n\n"
            f"Fix this by:\n"
            f"  1. Copying .env.example to .env in the project root "
            f"(if you haven't already)\n"
            f"  2. Setting {env_var}=<the real path> inside .env\n\n"
            f"Example: {env_var}=C:\\Users\\YourName\\Downloads\\best.pt"
        )
    return value


# ---------------------------------------------------------------------------
# Required paths - the app can't function without these, so they're
# validated at import time (fail fast, one clear message).
# ---------------------------------------------------------------------------
MODEL_PATH = _get_path("MODEL_PATH")
PR_FILE_PATH = _get_path("PR_FILE_PATH")

# ---------------------------------------------------------------------------
# Optional paths - the app degrades gracefully if these are missing.
# shared.py already falls back to a text placeholder when LOGO_PATH is
# empty or doesn't point to a file that exists.
# ---------------------------------------------------------------------------
LOGO_PATH = _get_path("LOGO_PATH", required=False)
