"""Score a learned compiler with the code every prompted compiler is already scored by.

**The one design decision in this file.** A learned prediction is turned into a
`CompiledScope` — the same pydantic model `LLMIntentCompiler` writes to disk — and handed to
`eval/scope_eval.compare_one`. Nothing here computes a rate. Leakage, retention, contrast
fidelity, over- and under-granting and the per-class table all come out of `scope_eval.build`,
unchanged, which is the function that produced every number `per-class` and `baseline` are
quoted at.

That is worth more than it looks. The alternative — a fresh metrics module for the learned
arm — would have been quicker and would have made the comparison worthless: two definitions
of "leakage" drift, and the one written by whoever is hoping the new model wins drifts in a
predictable direction. Reusing the scorer means a learned arm cannot be scored more kindly
than a prompted one even by accident.

**The same trick carries through to the verdict level.** Because the artifact is a real
`CompiledScope` jsonl, `agentfw replay` reads it with no changes at all, and the learned
compiler gets a *verdict*-level number from the same 621 committed episodes as everything
else. F-14 is the reason that matters: a compiler change is not an improvement until the
replay says so.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

from agentfw.eval import scope_eval
from agentfw.eval.scenario import Scenario, load_suite
from agentfw.eval.scopes import SCOPES_DIR
from agentfw.intent.compiler import CompiledScope
from agentfw.ml.dataset import LABEL_FILES, Dataset, Example
from agentfw.ml.models import Timing
from agentfw.sandbox.registry import load_all


def _gold_raw() -> dict[tuple[str, str], dict[str, Any]]:
    """The label files as `compare_one` wants them: keyed by (scenario, variant)."""
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for filename in LABEL_FILES.values():
        raw = yaml.safe_load((SCOPES_DIR / filename).read_text(encoding="utf-8")) or {}
        for scenario_id, variants in raw.items():
            for variant_id, body in (variants or {}).items():
                if isinstance(body, dict):
                    out[(scenario_id, variant_id)] = body
    return out


def as_compiled_scope(
    example: Example, predicted: set[str], *, label: str, seed: int = 1
) -> CompiledScope:
    """Wrap one prediction as the artifact type the rest of the project consumes.

    `constraints` is deliberately empty and `open_questions` deliberately empty. A learned
    rung here predicts an effect *set* and nothing else, so claiming either would be
    inventing a field. That has a visible cost — the ambiguity-flagging metric will read
    0.0% for every learned arm — and reporting that honestly is better than emitting a
    plausible-looking open question no model produced. It is also why Arm H exists: doubt is
    a separate question from membership.
    """
    return CompiledScope(
        scenario_id=example.scenario_id,
        variant_id=example.variant_id,
        compiler=label,
        model=label,
        seed=seed,
        prompt_variant="learned",
        prompt_version=1,
        utterance=example.text,
        effects=tuple(sorted(predicted)),
    )


def scope_records(
    examples: Sequence[Example], predictions: Sequence[set[str]], *, label: str
) -> list[CompiledScope]:
    return [
        as_compiled_scope(ex, pred, label=label)
        for ex, pred in zip(examples, predictions, strict=True)
    ]


def score(
    examples: Sequence[Example],
    predictions: Sequence[set[str]],
    *,
    label: str,
    scenarios: dict[str, Scenario] | None = None,
) -> dict[str, Any]:
    """Run the project's own scorer over a set of predictions."""
    if scenarios is None:
        load_all()
        scenarios = {s.id: s for s in load_suite(split=None)}
    gold = _gold_raw()
    rows = []
    for record, ex in zip(
        scope_records(examples, predictions, label=label), examples, strict=True
    ):
        rows.append(
            scope_eval.compare_one(
                record, scenarios[ex.scenario_id], gold[(ex.scenario_id, ex.variant_id)]
            )
        )
    return scope_eval.build(rows, label=label)


# ---------------------------------------------------------------------------
# the small handful of numbers a fold-level table needs
# ---------------------------------------------------------------------------


def headline(report: dict[str, Any]) -> dict[str, Any]:
    """Pull the four registered quantities out of a full scope_eval report."""
    contested = report.get("contested", {})

    def rate(block: Any) -> float | None:
        if isinstance(block, dict):
            value = block.get("value")
            return None if value is None else round(float(value), 4)
        return None

    return {
        "leakage_underspecified": rate(contested.get("leakage_underspecified_low")),
        "leakage_explicit_low": rate(contested.get("leakage_explicit_low")),
        "retention_high": rate(contested.get("retention_high")),
        "contrast_fidelity": rate(contested.get("contrast_fidelity")),
        "contrast_scenarios": (contested.get("contrast_fidelity") or {}).get("scenarios"),
    }


def exact_and_contested(
    examples: Sequence[Example], predictions: Sequence[set[str]]
) -> dict[str, Any]:
    """Prediction 37's two numbers: whole-set exactness, and the contested-class decision.

    Kept here rather than in `scope_eval` because they are E-15's questions and not the
    project's standing metrics. Exact-set match is reported against F-31's **80% human
    ceiling**, never against 100%.
    """
    exact = 0
    contested_total = 0
    contested_right = 0
    for ex, pred in zip(examples, predictions, strict=True):
        if set(ex.labels) == set(pred):
            exact += 1
        if ex.contested_class is not None and ex.contested_authorized is not None:
            contested_total += 1
            if (ex.contested_class in pred) == ex.contested_authorized:
                contested_right += 1
    return {
        "n": len(examples),
        "exact_set_match": round(exact / max(len(examples), 1), 4),
        "contested_decisions": contested_total,
        "contested_accuracy": (
            round(contested_right / contested_total, 4) if contested_total else None
        ),
    }


def per_class_leakage(
    examples: Sequence[Example], predictions: Sequence[set[str]]
) -> list[dict[str, Any]]:
    """Prediction 39: which contested classes leak, on low variants only."""
    import collections

    leaked: dict[str, int] = collections.Counter()
    total: dict[str, int] = collections.Counter()
    for ex, pred in zip(examples, predictions, strict=True):
        if ex.contested_class is None or ex.contested_authorized is not False:
            continue
        total[ex.contested_class] += 1
        if ex.contested_class in pred:
            leaked[ex.contested_class] += 1
    rows = [
        {
            "effect_class": klass,
            "low_variants": total[klass],
            "leaked": leaked.get(klass, 0),
            "rate": round(leaked.get(klass, 0) / total[klass], 4),
        }
        for klass in total
    ]
    return sorted(rows, key=lambda r: (-r["rate"], -r["low_variants"], r["effect_class"]))


def write_predictions(
    path: Path,
    examples: Sequence[Example],
    predictions: Sequence[set[str]],
    *,
    scheme: str,
    fold: str,
    rung: str,
) -> Path:
    """Every prediction, on disk, so an error analysis does not need a re-run."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for ex, pred in zip(examples, predictions, strict=True):
            fh.write(
                json.dumps(
                    {
                        "scheme": scheme,
                        "fold": fold,
                        "rung": rung,
                        "scenario_id": ex.scenario_id,
                        "variant_id": ex.variant_id,
                        "template": ex.template,
                        "world": ex.world,
                        "authority": ex.authority,
                        "specificity": ex.specificity,
                        "contested_class": ex.contested_class,
                        "contested_authorized": ex.contested_authorized,
                        "gold": sorted(ex.labels),
                        "predicted": sorted(pred),
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    return path


def fold_row(
    *,
    scheme: str,
    fold: str,
    rung: str,
    examples: Sequence[Example],
    predictions: Sequence[set[str]],
    timing: Timing,
    dataset_for_scoring: Dataset | None = None,
) -> dict[str, Any]:
    """One row of the results table, with everything a registered prediction needs."""
    del dataset_for_scoring  # scoring reads the committed labels directly
    report = score(examples, predictions, label=f"{rung}/{scheme}/{fold}")
    row: dict[str, Any] = {
        "scheme": scheme,
        "fold": fold,
        "rung": rung,
        "n_test": len(examples),
        "fit_s": timing.fit_s,
        "predict_s": timing.predict_s,
    }
    row.update(headline(report))
    row.update(exact_and_contested(examples, predictions))
    return row
