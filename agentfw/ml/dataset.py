"""E-15's dataset: the 293 blind-authored labels, as supervised examples.

**Where the labels come from, and why that is the interesting part.** Nothing here is
authored for machine learning. `dev.yaml` and `heldout_v3.yaml` are the *gold scopes* — a
human's statement of what each utterance licensed — and `heldout_v3.yaml` in particular was
written by an author who had seen no result and no run (D-033), against a brief that was
committed before any label existed. So the supervision is blind, and it is the same object
every compiled arm in this project has been scored against since Phase 3. That is what makes
a learned compiler comparable to a prompted one at all.

**It is also, therefore, small and fixed.** 293 labelled variants. There is no more, and
generating more would mean either paying a labeller or generating from the same 11 templates,
which is what the split design below exists to detect rather than to exploit.

**The feature is the utterance, and only the utterance.** D-025 restricts a compiler to the
user's turn and the tool catalogue; a compiler that reads a tool result can have its
authorization scope written by an attacker. That restriction is inherited here as the shape
of the record: `text` is the utterance, `candidates` is what the registered tools could
produce, and there is no field for anything the world said. The scenario id is carried for
joining and grouping and is **never** a feature (CLAUDE.md: gold scopes are labels, not
logic); `features()` returns text alone, which is what makes that checkable.

**The tool ceiling is a mask, not a feature.** `candidates` is the set of effect classes the
scenario's registered tools can produce, from `intent/catalog.py`. Intersecting a prediction
with it is the learned equivalent of showing the prompted compiler the tool list, which it
has always been shown. Measured cost of the mask: **1 of 293 variants** carries a gold label
its own tool list cannot produce, so the mask can cost at most one label and does not
meaningfully bound what a model is allowed to be right about.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from agentfw.eval.scenario import SUITE_DIR, Scenario, load_suite
from agentfw.eval.scopes import SCOPES_DIR
from agentfw.intent import catalog
from agentfw.sandbox.registry import load_all

# The two committed label files, and the split each one defines. These names are also the
# S1 split: train on everything from dev.yaml, test on everything from heldout_v3.yaml.
LABEL_FILES: dict[str, str] = {
    "dev": "dev.yaml",
    "heldout": "heldout_v3.yaml",
}

# A scenario that no template produced. Kept as an explicit token rather than None so it can
# be a group key in leave-one-template-out without special-casing.
HANDWRITTEN = "handwritten"

# Where the scenario templates live. Read directly, because the asking clause is a *slot*
# and the generated scenario keeps only the filled result.
TEMPLATE_DIR = SUITE_DIR.parent / "templates"


class Example(BaseModel):
    """One (utterance, licensed effect classes) pair, plus everything a split needs."""

    # -- identity, for joining back to a scope artifact. Never a feature. -----
    scenario_id: str
    variant_id: str

    # -- the input -----------------------------------------------------------
    text: str
    # Effect classes the scenario's registered tools could produce, sorted.
    candidates: tuple[str, ...] = ()

    # -- the target ----------------------------------------------------------
    labels: tuple[str, ...] = ()

    # -- grouping, for the three splits --------------------------------------
    split: str  # "dev" | "heldout"           -> S1
    world: str  # the world fixture           -> S2 (leave-one-world-out)
    template: str  # or HANDWRITTEN            -> S3 (leave-one-template-out)

    # -- context the analysis needs, none of it a feature ---------------------
    suite: str
    domain: str = ""
    authority: str = ""
    specificity: str = ""
    # The slot-filled asking clause this variant used, e.g. "Can you deal with that?".
    # None for a hand-written scenario, which has no template and therefore no slot. Used
    # only to define the S4 split; never a feature.
    ask_phrase: str | None = None
    # The class the scenario contests, e.g. "PURCHASE:FINANCIAL". None for benign/inject.
    contested_class: str | None = None
    # Structural ground truth (D-010): is the contested class licensed on this variant?
    contested_authorized: bool | None = None
    open_questions: tuple[str, ...] = ()

    def features(self) -> str:
        """The only thing a model is allowed to see.

        A method rather than an attribute so that a test can assert no identifier reaches
        the model: if this returned the record, a stray `scenario_id` would be invisible.
        """
        return self.text


class Dataset(BaseModel):
    examples: list[Example] = Field(default_factory=list)

    def __len__(self) -> int:
        return len(self.examples)

    def __iter__(self):  # type: ignore[override]
        return iter(self.examples)

    @property
    def classes(self) -> tuple[str, ...]:
        """Every effect class that appears as a label anywhere, sorted and fixed.

        The label space is closed over the *dataset*, not over the ontology: a class no
        labeller ever granted cannot be learned and should not silently become a column of
        zeros that flatters a macro average.
        """
        seen: set[str] = set()
        for ex in self.examples:
            seen |= set(ex.labels)
        return tuple(sorted(seen))

    def subset(self, examples: Iterable[Example]) -> Dataset:
        return Dataset(examples=list(examples))

    def write_jsonl(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(ex.model_dump_json() for ex in self.examples) + "\n", encoding="utf-8"
        )
        return path

    @classmethod
    def read_jsonl(cls, path: Path) -> Dataset:
        return cls(
            examples=[
                Example(**json.loads(line))
                for line in Path(path).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        )


def _tool_ceiling(scenario: Scenario) -> tuple[str, ...]:
    ceiling: set[str] = set()
    for tool in scenario.tools:
        for effect_class in catalog.TOOL_EFFECTS.get(tool, ()):
            ceiling.add(catalog.render(effect_class))
    return tuple(sorted(ceiling))


def ask_phrases() -> dict[tuple[str, str], str]:
    """(scenario_id, variant_id) -> the asking clause the template slotted in.

    Recovered from the templates rather than guessed from the text. A template's variant
    declares its utterance as a pattern like ``"{context} {us_ask}"``, so the slot name is
    read out of the pattern and looked up in the instance's own slots. Splitting on the
    last sentence would have been quicker and wrong: a context can be two sentences and an
    ask can be two clauses.

    This exists for one reason. Eight of the nine contested classes have a **sole** template
    source, so leave-one-template-out removes a class's positive examples at the same time
    as it removes its phrasings, and the S2-to-S3 gap therefore has two explanations at
    once. Holding out a *phrase* removes the phrasing and keeps the class, because the other
    instances of the same template use different phrases. That is what separates them.
    """
    import re

    out: dict[tuple[str, str], str] = {}
    for path in sorted(TEMPLATE_DIR.glob("*.yaml")):
        template = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        prefix = template.get("id_prefix")
        variants = template.get("variants") or []
        for instance in template.get("instances") or []:
            scenario_id = f"{prefix}.{instance['id_suffix']}"
            slots = instance.get("slots") or {}
            for variant in variants:
                pattern = str(variant.get("utterance", ""))
                names = [n for n in re.findall(r"{(\w+)}", pattern) if n.endswith("_ask")]
                if len(names) != 1:
                    continue
                value = slots.get(names[0])
                if value:
                    out[(scenario_id, str(variant["id"]))] = " ".join(str(value).split())
    return out


def _contested_class(scenario: Scenario) -> str | None:
    pattern = scenario.contested_effect
    if pattern is None or pattern.verb is None or pattern.resource_class is None:
        return None
    return f"{pattern.verb.value}:{pattern.resource_class.value}"


def build(scopes_dir: Path | None = None) -> Dataset:
    """Derive the dataset from the committed label files. Deterministic, no network.

    Raises rather than skipping when a label file names a scenario this build does not have.
    F-28 is the reason: a replay that silently skipped every episode once reported a perfect
    defense over zero of them, and a training set that silently loses half its rows is the
    same failure wearing different clothes.
    """
    load_all()
    scenarios = {s.id: s for s in load_suite(split=None)}
    root = scopes_dir or SCOPES_DIR
    phrases = ask_phrases()

    examples: list[Example] = []
    missing: list[str] = []
    for split, filename in LABEL_FILES.items():
        raw = yaml.safe_load((root / filename).read_text(encoding="utf-8")) or {}
        for scenario_id, variants in raw.items():
            scenario = scenarios.get(scenario_id)
            if scenario is None:
                missing.append(scenario_id)
                continue
            candidates = _tool_ceiling(scenario)
            contested = _contested_class(scenario)
            for variant_id, body in (variants or {}).items():
                if not isinstance(body, dict):
                    continue
                variant = scenario.variant(variant_id)
                examples.append(
                    Example(
                        scenario_id=scenario_id,
                        variant_id=variant_id,
                        text=" ".join(variant.utterance.split()),
                        candidates=candidates,
                        labels=tuple(sorted(set(body.get("effects") or []))),
                        split=split,
                        world=scenario.world.fixture,
                        template=scenario.template or HANDWRITTEN,
                        suite=scenario.suite,
                        domain=scenario.domain,
                        authority=variant.authority,
                        specificity=str(variant.specificity),
                        contested_class=contested,
                        contested_authorized=variant.contested_authorized,
                        ask_phrase=phrases.get((scenario_id, variant_id)),
                        open_questions=tuple(body.get("open_questions") or []),
                    )
                )
    if missing:
        raise ValueError(
            f"{len(missing)} scenario id(s) in the label files are unknown to this build: "
            f"{sorted(set(missing))[:5]}. Regenerate the suites or fix the labels; a "
            f"silently smaller dataset is how a result becomes fiction."
        )
    examples.sort(key=lambda e: (e.split, e.scenario_id, e.variant_id))
    return Dataset(examples=examples)


def summarise(data: Dataset) -> dict[str, object]:
    """Counts a reader would otherwise have to recompute to trust a table."""
    import collections

    labels = collections.Counter(c for ex in data for c in ex.labels)
    return {
        "n_examples": len(data),
        "n_distinct_texts": len({ex.text for ex in data}),
        "n_classes": len(data.classes),
        "mean_labels": round(sum(len(ex.labels) for ex in data) / max(len(data), 1), 3),
        "by_split": dict(collections.Counter(ex.split for ex in data)),
        "by_world": dict(collections.Counter(ex.world for ex in data)),
        "by_template": dict(collections.Counter(ex.template for ex in data)),
        "by_suite": dict(collections.Counter(ex.suite for ex in data)),
        "label_counts": dict(labels.most_common()),
        "labels_outside_tool_ceiling": sum(
            1 for ex in data if set(ex.labels) - set(ex.candidates)
        ),
        "contested_positive": sum(1 for ex in data if ex.contested_authorized is True),
        "contested_negative": sum(1 for ex in data if ex.contested_authorized is False),
        "n_ask_phrases": len({ex.ask_phrase for ex in data if ex.ask_phrase}),
        "n_with_ask_phrase": sum(1 for ex in data if ex.ask_phrase),
    }
