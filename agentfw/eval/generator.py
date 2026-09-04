"""Scenario generator.

RISK R-07: scenario authoring is slow, Phase 5 needs ~120-200 AF-Auth scenarios, and
projects like this die when that work is left to the end. So the generator exists now, in
Phase 1, and Phase 5 becomes scaling rather than inventing.

**That mitigation did not hold, and this module is the repair (Phase 3.5).** The generator
shipped with one template and it produced the wrong shape: an explicit *pair* --- "draft a
reply to X" against "reply to X" --- when the phenomenon the benchmark was re-centred on in
D-018 lives in the underspecified *triple*. The held-out suite it produced therefore had
zero underspecified variants and could not exercise the band the project is about (D-031).
Having a generator was not the same as having the right generator, and the failure was
invisible because nothing forced a template to say what shape it made.

So a template no longer knows about "low" and "high" as special names. **It declares its
variants**, each with its own authority, specificity and oracle, and the same machinery
makes a pair, a triple, or whatever the schema will validate. The four special-cased fields
(`low_utterance`, `high_utterance`, and their two oracles) are gone rather than joined by
four more --- a triple template written on top of them would have needed
`underspecified_utterance` and a third oracle, and a quadruple another two.

A template is one *scenario shape* --- a contested effect, a tool set, and the utterance
forms that differ only in the authority they license --- plus a table of instances that fill
its slots. Substitution is recursive over strings in the template body, so oracles get filled
in too, and every generated scenario is validated by the same pydantic model as a
hand-written one and passes the same gates: oracle triviality (F-01), effect reachability,
and findability (F-20). Generated scenarios are marked ``source: generated`` and carry the
template name, so a later analysis can check whether the generated half behaves like the
hand-written half --- if it does not, the generator is producing artefacts and we will see it
rather than assume it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentfw.eval.scenario import Role, Scenario, Specificity, Split, Suite

TEMPLATE_DIR = Path(__file__).parent / "templates"
_SLOT = re.compile(r"\{([a-z0-9_]+)\}")


class Instance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_suffix: str
    domain: str | None = None
    slots: dict[str, str] = Field(default_factory=dict)
    world_overlay: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""


class VariantTemplate(BaseModel):
    """One utterance form. The template says what it is; the generator does not guess.

    The *play* that satisfies this variant lives in the template's ``plays`` block rather
    than here, keyed by variant id — one reviewable table per shape instead of a fragment
    buried in each variant.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    authority: str
    specificity: Specificity = "explicit"
    contested_authorized: bool | None = None
    utterance: str
    task_oracle: dict[str, Any] | None = None
    notes: str = ""


class Play(BaseModel):
    """What an ideal agent would do, and say, to satisfy one variant's oracle.

    Not decoration. F-05, F-20 and F-21 were each an unsatisfiable task dressed as a model
    failure, and each was found only after it had cost a run. The gate that catches that
    class asks whether *some* trajectory satisfies the oracle, and Phase 3.5 answered it with
    a table of 60 plays maintained by hand beside the suite. At Phase 5's size (D-036: 60-100
    core triples) a hand-maintained table is precisely the thing that stops being maintained,
    so the template carries it and every instance gets a gate for free.
    """

    model_config = ConfigDict(extra="forbid")

    play: list[dict[str, Any]] = Field(default_factory=list)
    says: str = ""


class ScenarioTemplate(BaseModel):
    """One scenario shape plus the instances that fill it."""

    model_config = ConfigDict(extra="forbid")

    template: str
    suite: Suite = "af_auth"
    family: str
    role: Role = "core"
    domain: str
    id_prefix: str
    split: Split = "heldout"
    fixture: str = "office_baseline"
    tools: list[str]
    max_steps: int = 12
    description: str = ""
    contested_effect: dict[str, Any] | None = None
    variants: list[VariantTemplate]
    # variant id -> the ideal play for it. Carried by the template so that every instance
    # gets a gate for free (F-30, D-036): the gates that survive scaling are the ones the
    # generator emits, not the ones a person maintains alongside it.
    plays: dict[str, Play] = Field(default_factory=dict)
    instances: list[Instance]

    @model_validator(mode="after")
    def _check(self) -> ScenarioTemplate:
        if not self.variants:
            raise ValueError(f"{self.template}: a template with no variants makes nothing")
        ids = [v.id for v in self.variants]
        if len(set(ids)) != len(ids):
            raise ValueError(f"{self.template}: duplicate variant ids {ids}")
        # The shape rules themselves live on Scenario, which validates every expansion. What
        # is worth catching here is the mistake this module exists to prevent: a template
        # that claims to make triples and makes pairs.
        unknown = set(self.plays) - {v.id for v in self.variants}
        if unknown:
            raise ValueError(f"{self.template}: plays for unknown variants {sorted(unknown)}")
        if self.plays and len(self.plays) != len(self.variants):
            missing = {v.id for v in self.variants} - set(self.plays)
            raise ValueError(
                f"{self.template}: declares plays for some variants and not {sorted(missing)}. "
                f"A partial play table is the state a hand-maintained one decays into, which "
                f"is the reason the template carries it at all (F-30)."
            )
        if self.suite == "af_auth" and len(self.variants) == 3:
            specs = sorted(v.specificity for v in self.variants if v.authority == "low")
            if specs != ["explicit", "underspecified"]:
                raise ValueError(
                    f"{self.template}: a three-variant af_auth template must contrast one "
                    f"underspecified low variant against one explicit low variant, got "
                    f"{specs}. That contrast is the phenomenon; a template that loses it "
                    f"produces scenarios that look like the dev slice and measure nothing "
                    f"it measures (D-018, D-031)."
                )
        return self

    @classmethod
    def from_yaml(cls, path: Path) -> ScenarioTemplate:
        return cls(**(yaml.safe_load(path.read_text(encoding="utf-8")) or {}))


# Retained name so existing callers and configs keep working; the shape is the general one.
PairTemplate = ScenarioTemplate


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


def expand_plays(tpl: ScenarioTemplate) -> dict[str, dict[str, Any]]:
    """``"<scenario id>::<variant id>" -> {"play": [...], "says": "..."}`` for one template."""
    out: dict[str, dict[str, Any]] = {}
    for inst in tpl.instances:
        slots = dict(inst.slots)
        sid = f"{tpl.id_prefix}.{inst.id_suffix}"
        for vid, spec in tpl.plays.items():
            out[f"{sid}::{vid}"] = {
                "play": [_fill(step, slots) for step in spec.play],
                "says": _fill(spec.says, slots),
            }
    return out


def expand(tpl: ScenarioTemplate) -> list[Scenario]:
    out: list[Scenario] = []
    for inst in tpl.instances:
        slots = dict(inst.slots)
        data: dict[str, Any] = {
            "id": f"{tpl.id_prefix}.{inst.id_suffix}",
            "suite": tpl.suite,
            "family": tpl.family,
            "role": tpl.role,
            "domain": inst.domain or tpl.domain,
            "split": tpl.split,
            "source": "generated",
            "template": tpl.template,
            "tools": list(tpl.tools),
            "max_steps": tpl.max_steps,
            "world": {"fixture": tpl.fixture, "overlay": _fill(inst.world_overlay, slots)},
            "notes": inst.notes or tpl.description,
            "variants": [
                {
                    "id": v.id,
                    "authority": v.authority,
                    "specificity": v.specificity,
                    "contested_authorized": v.contested_authorized,
                    "utterance": _fill(v.utterance, slots),
                    "task_oracle": _fill(v.task_oracle, slots) if v.task_oracle else None,
                    "notes": _fill(v.notes, slots),
                }
                for v in tpl.variants
            ],
        }
        if tpl.contested_effect is not None:
            data["contested_effect"] = _fill(tpl.contested_effect, slots)
        out.append(Scenario(**data))
    return out


def expand_dir(template_dir: Path | None = None) -> list[Scenario]:
    template_dir = template_dir or TEMPLATE_DIR
    out: list[Scenario] = []
    for path in sorted(template_dir.glob("*.yaml")):
        out += expand(ScenarioTemplate.from_yaml(path))
    return out


PLAYS_DIR = Path(__file__).parent / "plays"


def expand_plays_dir(template_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    template_dir = template_dir or TEMPLATE_DIR
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(template_dir.glob("*.yaml")):
        out.update(expand_plays(ScenarioTemplate.from_yaml(path)))
    return out


def write_plays(plays: dict[str, dict[str, Any]], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "# GENERATED FILE - produced by `agentfw generate`. Do not hand-edit;\n"
    text += "# the ideal play lives in the template beside the utterance it satisfies.\n"
    text += yaml.safe_dump(plays, sort_keys=True, allow_unicode=True, width=88)
    path.write_text(text, encoding="utf-8")
    return len(plays)


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


def write_suites(scenarios: list[Scenario], root: Path) -> dict[Path, int]:
    """Write one file per (suite, split), so generated scenarios land beside their kin."""
    groups: dict[tuple[str, str], list[Scenario]] = {}
    for s in scenarios:
        groups.setdefault((s.suite, s.split), []).append(s)
    written: dict[Path, int] = {}
    for (suite, split), group in sorted(groups.items()):
        path = root / suite / f"generated_{split}.yaml"
        written[path] = write_suite(sorted(group, key=lambda s: s.id), path)
    return written
