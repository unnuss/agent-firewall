"""Scenario schema and loader.

Built in Phase 1 on purpose. Scenario authoring is where projects like this die
(ROADMAP "Sequencing risks", RISK R-07), so the *format* and the *generator* exist now and
Phase 5 is scaling rather than inventing.

The AF-Auth shape is the minimal pair (D-010): one world, one tool set, two utterances
that differ only in the consequence they license. Ground truth is therefore structural —
nobody has to label "was this risky?", which is the annotation problem that put a
Fleiss-kappa 0.52 noise floor under prior work.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentfw.eval.oracles import EffectPattern, Oracle

SUITE_DIR = Path(__file__).parent / "suites"

Suite = Literal["af_auth", "af_inject", "benign"]
Split = Literal["dev", "heldout"]


class WorldRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fixture: str = "office_baseline"
    overlay: dict[str, Any] = Field(default_factory=dict)


class Variant(BaseModel):
    """One utterance over the shared world."""

    model_config = ConfigDict(extra="forbid")

    id: str
    authority: Literal["low", "high"]
    utterance: str
    # Does this utterance license the scenario's contested effect? For a minimal pair this
    # is False for the low variant and True for the high variant, by construction.
    # Only meaningful for af_auth; None elsewhere.
    contested_authorized: bool | None = None
    # What a correct agent should have achieved *under this utterance*.
    task_oracle: Oracle | None = None
    notes: str = ""


class Attack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: Literal["T1", "T2", "T3"] = "T1"
    channel: Literal["web", "email", "doc", "calendar"] = "web"
    goal: str
    success_oracle: Oracle


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    suite: Suite
    family: str  # B1..B5 for af_auth, A1..A6 for af_inject, "benign" otherwise
    domain: str
    split: Split = "dev"
    source: Literal["handwritten", "generated"] = "handwritten"
    template: str | None = None
    tools: list[str]
    world: WorldRef = Field(default_factory=WorldRef)
    max_steps: int = 12
    # AF-Auth: the effect whose authorization differs between variants.
    contested_effect: EffectPattern | None = None
    variants: list[Variant]
    attack: Attack | None = None
    notes: str = ""

    @model_validator(mode="after")
    def _check_shape(self) -> Scenario:
        ids = [v.id for v in self.variants]
        if len(set(ids)) != len(ids):
            raise ValueError(f"{self.id}: duplicate variant ids {ids}")
        if self.suite == "af_auth":
            if self.contested_effect is None:
                raise ValueError(f"{self.id}: af_auth scenario needs a contested_effect")
            if len(self.variants) != 2:
                raise ValueError(f"{self.id}: a minimal pair needs exactly 2 variants")
            lo = [v for v in self.variants if v.authority == "low"]
            hi = [v for v in self.variants if v.authority == "high"]
            if len(lo) != 1 or len(hi) != 1:
                raise ValueError(f"{self.id}: need one low and one high authority variant")
            if (
                lo[0].contested_authorized is not False
                or hi[0].contested_authorized is not True
            ):
                raise ValueError(
                    f"{self.id}: contested_authorized must be False for the low variant "
                    "and True for the high variant — that is what makes the pair minimal"
                )
        if self.suite == "af_inject" and self.attack is None:
            raise ValueError(f"{self.id}: af_inject scenario needs an attack block")
        if self.suite != "af_auth" and len(self.variants) != 1:
            raise ValueError(f"{self.id}: non-paired suites take exactly one variant")
        return self

    def variant(self, vid: str) -> Variant:
        for v in self.variants:
            if v.id == vid:
                return v
        raise KeyError(f"{self.id}: no variant {vid!r}")


def load_scenarios(path: Path) -> list[Scenario]:
    """A scenario file may hold one scenario or several, separated by ``---``."""
    docs = [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]
    out = []
    for i, doc in enumerate(docs):
        try:
            out.append(Scenario(**doc))
        except Exception as exc:
            raise ValueError(f"{path.name} document {i}: {exc}") from exc
    return out


def load_scenario(path: Path) -> Scenario:
    scenarios = load_scenarios(path)
    if len(scenarios) != 1:
        raise ValueError(f"{path} holds {len(scenarios)} scenarios; use load_scenarios")
    return scenarios[0]


def load_suite(
    suite: Suite | None = None,
    *,
    split: Split | None = "dev",
    root: Path | None = None,
) -> list[Scenario]:
    root = root or SUITE_DIR
    globs = sorted((root / suite).rglob("*.yaml")) if suite else sorted(root.rglob("*.yaml"))
    out: list[Scenario] = []
    for p in globs:
        out += load_scenarios(p)
    ids = [s.id for s in out]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate scenario ids: {sorted(dupes)}")
    if split is not None:
        out = [s for s in out if s.split == split]
    return sorted(out, key=lambda s: s.id)


def save_scenario(scenario: Scenario, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = scenario.model_dump(mode="json", exclude_none=True, exclude_defaults=False)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=88),
        encoding="utf-8",
    )
