"""Local credential loading.

Why this exists: a long-running process inherits its environment at start-up, so rotating
a key in a terminal does not reach it. Rather than requiring a restart mid-experiment, the
CLI reads an optional gitignored ``.env.local`` at the repository root.

Rules: values are only ever *set*, never printed, and an existing environment variable
always wins over the file, so the file cannot silently shadow a deliberately exported key.
``.gitignore`` already excludes ``.env`` and ``.env.*``.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env.local"


def load_local_env(path: Path | None = None, *, override: bool = False) -> list[str]:
    """Load KEY=VALUE lines from .env.local. Returns the names loaded, never the values."""
    path = path or ENV_FILE
    if not path.exists():
        return []
    loaded: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key or (not override and os.environ.get(key)):
            continue
        os.environ[key] = value
        loaded.append(key)
    return loaded
