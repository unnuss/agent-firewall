"""Compiled scopes on disk, and the seam that lets a replay use them.

**Why the compilation is an artifact rather than a call.** E-01b replays 702 episodes; the
86 distinct (scenario, variant) utterances behind them would otherwise be compiled hundreds
of times over, at real cost and with real sampling noise between passes. Compiling once,
committing the result, and replaying from the file makes the experiment a **pure function
of files in the repository** — the same property that lets E-01a reproduce with no API key
and no dollars — and it keeps the compiler's sampling variance where it belongs, measured
across seeds rather than smeared through the replay.

The store presents the same ``scope_for`` interface as ``eval/scopes.GoldScopes``, so the
replay harness takes either one and the only difference between the gold arm and a compiled
arm of E-01b is which object was passed in.
"""

from __future__ import annotations

import json
from pathlib import Path

from agentfw.core.scope import IntentScope
from agentfw.intent.compiler import CompiledScope


class MissingCompiledScope(KeyError):
    """No compilation for this variant. Fail loudly, exactly as a missing gold scope does:
    defaulting to an empty scope would turn an operational gap into a security result."""


class CompiledScopeStore:
    """scenario_id -> variant_id -> CompiledScope, loaded from one JSONL file."""

    def __init__(self, records: list[CompiledScope], *, label: str = "") -> None:
        self.records = records
        self.label = label
        self.index: dict[tuple[str, str], CompiledScope] = {
            (r.scenario_id, r.variant_id): r for r in records
        }

    @classmethod
    def load(cls, path: Path, *, label: str = "") -> CompiledScopeStore:
        records = [
            CompiledScope(**json.loads(line))
            for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return cls(records, label=label or Path(path).stem)

    @staticmethod
    def write(records: list[CompiledScope], path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(r.model_dump_json() for r in records) + "\n", encoding="utf-8"
        )
        return path

    # -- the ScopeSource interface -----------------------------------------

    def scope_for(self, scenario_id: str, variant_id: str, objective: str) -> IntentScope:
        try:
            record = self.index[(scenario_id, variant_id)]
        except KeyError as exc:
            raise MissingCompiledScope(
                f"no compiled scope for {scenario_id}::{variant_id} in {self.label!r}"
            ) from exc
        return record.to_scope(objective)

    def covers(self, scenario_id: str, variant_id: str) -> bool:
        return (scenario_id, variant_id) in self.index

    # -- diagnostics --------------------------------------------------------

    @property
    def errors(self) -> list[CompiledScope]:
        return [r for r in self.records if r.error]

    def usage(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in self.records:
            for k, v in r.usage.items():
                out[k] = out.get(k, 0) + int(v)
        return out
