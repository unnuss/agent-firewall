"""D-041's two arms, as committed artifacts the rest of the project already knows how to read.

**Arm L — learned-as-compiler.** Fit on the S1 training split (`dev`, 86 hand-written
labels), predict the 207 held-out utterances, and write the result as a `CompiledScope`
jsonl. The file is byte-for-byte the same *kind* of object `agentfw compile-scopes` writes
for a prompted arm, so `agentfw replay` reads it with no change at all and the learned
compiler gets a verdict-level number over the same 621 committed episodes as everything
else. F-14 is why that matters: a compiler change is not an improvement until the replay
says so.

**Arm H — learned-as-narrowing-signal.** The intersection of a *prompted* scope with the
learned model's prediction:

    arm_h(v) = prompted_effects(v)  &  learned_prediction(v)

Intersection is the whole design. It cannot add a class, so no learned output can ever
become authority the monitor did not already have from a prompted compiler — which is
D-038's "may never grant" taken literally, and is why this arm is safe under any reading of
D-006. A test asserts the subset relation on every variant rather than trusting the operator.

**Arm H's ancestor, and the bar it has to clear.** E-12 built the lexical version of this:
withhold the grants the compiler itself questioned in its own open-questions field. D-035
measured it at N=60 and **did not adopt it** — it turned out to be a substitute for
`per-class` rather than a complement, and it degraded the best arm. Prediction 40 asks
whether a trained doubt-detector does better than a word list. It has a real precedent to
beat and it is allowed to fail.

**The training split is not negotiable here.** Arm H filters the held-out scopes, so the
model that does the filtering must never have seen a held-out label. It is fitted on `dev`
alone, exactly as Arm L is.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentfw.intent.compiler import CompiledScope
from agentfw.intent.store import CompiledScopeStore
from agentfw.ml import evaluate, models, splits
from agentfw.ml.dataset import Dataset, Example


def fit_on_dev(rung_name: str, data: Dataset) -> tuple[Any, list[Example], list[set[str]]]:
    """Fit one rung on S1's training half and predict its test half.

    Returns the fitted rung plus the held-out examples and predictions, because both arms
    need the same prediction and re-fitting for the second one would be a second experiment.
    """
    fold = splits.folds(data, "S1")[0]
    rung = models.build_rung(rung_name)
    predictions, _ = models.fit_and_predict(rung, fold.train, fold.test)
    return rung, list(fold.test), predictions


def write_arm_l(
    examples: list[Example], predictions: list[set[str]], path: Path, *, label: str
) -> Path:
    """Arm L: the learned prediction, as a compiled-scope artifact."""
    records = evaluate.scope_records(examples, predictions, label=label)
    return CompiledScopeStore.write(records, path)


def narrow(prompted: CompiledScope, predicted: set[str]) -> CompiledScope:
    """Arm H on one variant: keep only what the prompted scope granted *and* the model kept.

    The open question is appended rather than replacing the prompted one, because the
    prompted compiler's own doubts are evidence too and dropping them would make Arm H look
    like it had discovered something the prompted arm already knew.
    """
    kept = tuple(sorted(set(prompted.effects) & predicted))
    withheld = sorted(set(prompted.effects) - predicted)
    if not withheld:
        return prompted.model_copy(deep=True)
    return prompted.model_copy(
        deep=True,
        update={
            "effects": kept,
            "open_questions": prompted.open_questions
            + tuple(
                f"whether {klass} was authorized: the prompted compiler granted it and the "
                f"learned compiler did not"
                for klass in withheld
            ),
        },
    )


def write_arm_h(
    prompted_path: Path,
    examples: list[Example],
    predictions: list[set[str]],
    path: Path,
) -> tuple[Path, dict[str, Any]]:
    """Arm H: filter a committed prompted artifact through the learned prediction."""
    store = CompiledScopeStore.load(prompted_path)
    predicted_by_key = {
        (ex.scenario_id, ex.variant_id): pred
        for ex, pred in zip(examples, predictions, strict=True)
    }
    out: list[CompiledScope] = []
    withheld_total = 0
    untouched = 0
    unseen = 0
    for record in store.records:
        key = (record.scenario_id, record.variant_id)
        if key not in predicted_by_key:
            # A variant the learned model has no prediction for is passed through
            # unchanged. Withholding on absence would be the learned arm taking credit for
            # an outage, which is the F-28 failure in a different costume.
            unseen += 1
            out.append(record.model_copy(deep=True))
            continue
        filtered = narrow(record, predicted_by_key[key])
        withheld = len(set(record.effects)) - len(set(filtered.effects))
        withheld_total += withheld
        if withheld == 0:
            untouched += 1
        out.append(filtered)
    CompiledScopeStore.write(out, path)
    return path, {
        "records": len(out),
        "classes_withheld": withheld_total,
        "variants_untouched": untouched,
        "variants_without_a_prediction": unseen,
    }


def build_arms(
    data: Dataset,
    rung_name: str,
    prompted_path: Path,
    out_dir: Path,
) -> dict[str, Any]:
    """Write both arms and score both with the project's own scorer."""
    out_dir.mkdir(parents=True, exist_ok=True)
    _, examples, predictions = fit_on_dev(rung_name, data)

    arm_l_path = out_dir / f"armL-{rung_name}.s1.jsonl"
    write_arm_l(examples, predictions, arm_l_path, label=f"armL-{rung_name}")
    arm_l_report = evaluate.score(examples, predictions, label=f"armL-{rung_name}")

    arm_h_path = out_dir / f"armH-{rung_name}-over-per-class.s1.jsonl"
    _, arm_h_stats = write_arm_h(prompted_path, examples, predictions, arm_h_path)

    # Score Arm H from its own artifact, so it is scored as the file a replay would read
    # rather than as an in-memory object that might differ from what was written.
    arm_h_store = CompiledScopeStore.load(arm_h_path)
    arm_h_predictions = [
        set(arm_h_store.index[(ex.scenario_id, ex.variant_id)].effects)
        if (ex.scenario_id, ex.variant_id) in arm_h_store.index
        else set()
        for ex in examples
    ]
    arm_h_report = evaluate.score(examples, arm_h_predictions, label=f"armH-{rung_name}")

    # And the prompted arm it filters, on exactly the same examples, so the comparison is a
    # difference and not two numbers from different denominators.
    prompted_store = CompiledScopeStore.load(prompted_path)
    prompted_predictions = [
        set(prompted_store.index[(ex.scenario_id, ex.variant_id)].effects)
        if (ex.scenario_id, ex.variant_id) in prompted_store.index
        else set()
        for ex in examples
    ]
    prompted_report = evaluate.score(examples, prompted_predictions, label="prompted")

    result = {
        "rung": rung_name,
        "prompted_source": str(prompted_path),
        "n_examples": len(examples),
        "arm_L": {
            "artifact": str(arm_l_path),
            **evaluate.headline(arm_l_report),
            **evaluate.exact_and_contested(examples, predictions),
        },
        "arm_H": {
            "artifact": str(arm_h_path),
            **evaluate.headline(arm_h_report),
            **evaluate.exact_and_contested(examples, arm_h_predictions),
            **arm_h_stats,
        },
        "prompted_baseline": {
            "artifact": str(prompted_path),
            **evaluate.headline(prompted_report),
            **evaluate.exact_and_contested(examples, prompted_predictions),
        },
    }
    (out_dir / "arms.json").write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    return result
