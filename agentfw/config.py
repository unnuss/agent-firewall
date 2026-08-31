"""Local credential loading.

Why this exists: a long-running process inherits its environment at start-up, so rotating
a key in a terminal does not reach it. Rather than requiring a restart mid-experiment, the
CLI reads an optional gitignored ``.env.local`` at the repository root.

**Precedence, reversed 2026-08-31 (D-029), because the old rule cost a run.** The original
rule was that an exported environment variable always wins, so that the file "cannot
silently shadow a deliberately exported key". That is one direction of a symmetric problem,
and the other direction is the one that actually happened: a *stale* exported
``OPENAI_API_KEY`` — a different key from the one in ``.env.local``, on an account with no
credit — silently shadowed the working key the operator had put in the file. Every layer
reported success (``has_openai_key: true``), the provider returned
``credit_balance_exhausted``, and E-09a's registered arm was recorded as blocked on billing
for a day when it was blocked on credential precedence.

So the rule now is: **``.env.local`` wins, and a disagreement is announced.** The file is
the repository's own statement of which credential this project uses; editing it is a
deliberate act, and it is the only one of the two that a reader of the repo can see. Pass
``prefer_environment=True`` (CLI: ``--prefer-exported-key``) for the old behaviour.

Two rules that did not change and should not:

* **Values are only ever set, never printed.** Anything user-facing gets a
  :func:`fingerprint` — a truncated hash — so that "which key did that run use?" is
  answerable from a log without the log containing a key.
* Nothing here reads a credential out of anything but the environment and this file.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env.local"


def fingerprint(value: str | None) -> str:
    """A stable, non-reversible identifier for a secret, safe to print and to commit.

    Enough to answer "is this the same key as last time?" and "is it the one in the file?",
    and useless to anybody who obtains it.
    """
    if value is None:
        return "absent"
    if not value:
        return "empty"
    return f"sha8:{hashlib.sha256(value.encode()).hexdigest()[:8]}"


@dataclass
class CredentialLoad:
    """What happened when the file met the environment. Printed at the top of every run."""

    #: Names whose value now comes from ``.env.local``.
    loaded: list[str] = field(default_factory=list)
    #: Names present in both, holding the *same* value. Nothing to decide.
    agreed: list[str] = field(default_factory=list)
    #: Names present in both with *different* values, and which source won.
    conflicts: list[tuple[str, str]] = field(default_factory=list)

    def summary(self) -> str:
        parts = []
        if self.loaded:
            parts.append("loaded " + ", ".join(self.loaded) + " from .env.local")
        if self.agreed:
            parts.append(", ".join(self.agreed) + " already matched the environment")
        return "; ".join(parts)

    def warnings(self) -> list[str]:
        """Lines a caller must show. A shadowed credential is never allowed to be quiet."""
        out = []
        for name, winner in self.conflicts:
            other = (
                "the exported environment variable" if winner == ".env.local" else ".env.local"
            )
            out.append(
                f"{name}: .env.local and the exported environment hold DIFFERENT values. "
                f"Using the one from {winner} (D-029); {other} is ignored for this run."
            )
        return out


def load_local_env(
    path: Path | None = None,
    *,
    prefer_environment: bool = False,
) -> CredentialLoad:
    """Load KEY=VALUE lines from .env.local. Returns a report, never a value."""
    report = CredentialLoad()
    path = path or ENV_FILE
    if not path.exists():
        return report
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        existing = os.environ.get(key)
        if existing is None or existing == "":
            os.environ[key] = value
            report.loaded.append(key)
        elif existing == value:
            report.agreed.append(key)
        elif prefer_environment:
            report.conflicts.append((key, "the exported environment variable"))
        else:
            os.environ[key] = value
            report.loaded.append(key)
            report.conflicts.append((key, ".env.local"))
    return report


def credential_report() -> dict[str, str]:
    """Which credentials are visible, by fingerprint. Safe to print and to commit.

    ``has_openai_key: true`` was the whole of the old report, and it was true throughout the
    incident that produced D-029 — of the wrong key. A fingerprint distinguishes them.
    """
    return {
        name: fingerprint(os.environ.get(name))
        for name in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY")
    }
