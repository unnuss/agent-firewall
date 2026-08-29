"""Scenario generator.

RISK R-07: scenario authoring is slow, Phase 5 needs ~120-200 AF-Auth scenarios, and
projects like this die when that work is left to the end. So the generator exists now, in
Phase 1, and Phase 5 becomes scaling rather than inventing.

A template is one *pair shape* — a contested effect, a tool set, and two utterance forms
that differ only in the consequence they license — plus a table of instances that fill its
slots. Substitution is recursive over strings in the template body, so oracles get filled
in too, and every generated scenario is validated by the same pydantic model as a
hand-written one. Generated scenarios are marked ``source: generated`` and carry the
template name, so a later analysis can check whether the generated half behaves like the
hand-written half — if it does not, the generator is producing artefacts and we will see
it rather than assume it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from agentfw.eval.scenario import Scenario, Split

TEMPLATE_DIR = Path(__file__).parent / "templates"
_SLOT = re.compile(r"\{([a-z0-9_]+)\}")


class Instance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_suffix: str
    domain: str | None = None
    slots: dict[str, str] = Field(default_factory=dict)
    world_overlay: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""


class PairTemplate(BaseModel):
    """One AF-Auth pair shape plus the instances that fill it."""

    model_config = ConfigDict(extra="forbid")

    template: str
    family: str
    domain: str
    id_prefix: str
    split: Split = "heldout"
    fixture: str = "office_baseline"
    tools: list[str]
    max_steps: int = 12
    description: str = ""
    contested_effect: dict[str, Any]
    low_utterance: str
    high_utterance: str
    low_task_oracle: dict[str, Any] | None = None
    high_task_oracle: dict[str, Any] | None = None
    instances: list[Instance]

    @classmethod
    def from_yaml(cls, path: Path) -> PairTemplate:
        return cls(**(yaml.safe_load(path.read_text(encoding="utf-8")) or {}))


def _fill(value: Any, slots: dict[str, str]) -> Any:
    if isinstance(value, str):
        missing = {m for m in _SLOT.findall(value) if m not in slots}
        if missing:
            raise KeyError(f"template slot(s) {sorted(missing)} not provided for {value!r}")
        return value.format(**slots)
    if isinstance(value, dict):
        return {k: _fill(v, slots) for k, v in value.items()}
    if isinstance(value, list):
        return [_fill(v, slots) for v in value]
    return value


def expand(tpl: PairTemplate) -> list[Scenario]:
    out: list[Scenario] = []
    for inst in tpl.instances:
        slots = dict(inst.slots)
        data: dict[str, Any] = {
            "id": f"{tpl.id_prefix}.{inst.id_suffix}",
            "suite": "af_auth",
            "family": tpl.family,
            "domain": inst.domain or tpl.domain,
            "split": tpl.split,
            "source": "generated",
            "template": tpl.template,
            "tools": list(tpl.tools),
            "max_steps": tpl.max_steps,
            "world": {"fixture": tpl.fixture, "overlay": _fill(inst.world_overlay, slots)},
            "contested_effect": _fill(tpl.contested_effect, slots),
            "notes": inst.notes or tpl.description,
            "variants": [
                {
                    "id": "a",
                    "authority": "low",
                    "contested_authorized": False,
                    "utterance": _fill(tpl.low_utterance, slots),
                    "task_oracle": _fill(tpl.low_task_oracle, slots)
                    if tpl.low_task_oracle
                    else None,
                },
                {
                    "id": "b",
                    "authority": "high",
                    "contested_authorized": True,
                    "utterance": _fill(tpl.high_utterance, slots),
                    "task_oracle": _fill(tpl.high_task_oracle, slots)
                    if tpl.high_task_oracle
                    else None,
                },
            ],
        }
        out.append(Scenario(**data))
    return out


def expand_dir(template_dir: Path | None = None) -> list[Scenario]:
    template_dir = template_dir or TEMPLATE_DIR
    out: list[Scenario] = []
    for path in sorted(template_dir.glob("*.yaml")):
        out += expand(PairTemplate.from_yaml(path))
    return out


def write_suite(scenarios: list[Scenario], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    docs = [
        s.model_dump(mode="json", exclude_none=True, exclude_defaults=False) for s in scenarios
    ]
    text = "# GENERATED FILE — produced by `agentfw generate`. Do not hand-edit;\n"
    text += "# change the template under agentfw/eval/templates/ and regenerate.\n"
    text += yaml.safe_dump_all(docs, sort_keys=False, allow_unicode=True, width=88)
    path.write_text(text, encoding="utf-8")
    return len(scenarios)
