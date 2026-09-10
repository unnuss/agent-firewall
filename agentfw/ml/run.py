"""E-15's grid: every rung against every split, written to disk as it goes.

**Why a runner rather than a notebook.** Every table in the README must be regenerable by
one command (CLAUDE.md), and a result that exists only in a terminal scrollback is not a
result. This writes `rows.jsonl` (one row per rung x fold), `predictions.jsonl` (every
prediction, so an error analysis never needs a re-run) and `report.md`, next to the config
that produced them.

**Folds are scored, never pooled.** S1 has one fold and S2 and S3 have four and eleven. A
mean over S3's folds weights an 6-example template the same as an 18-example one, so the
report gives both the per-fold rows and a **pooled** figure computed by concatenating every
fold's predictions and scoring the concatenation once — which is the same denominator S1
uses and is the only one comparable to it.
"""

from __future__ import annotations

import json
import platform
import sys
import time
from pathlib import Path
from typing import Any

from agentfw.ml import evaluate, models, splits
from agentfw.ml.dataset import Dataset, Example, build, summarise


def run_grid(
    data: Dataset,
    rung_names: list[str],
    schemes: list[str],
    out_dir: Path,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = out_dir / "predictions.jsonl"
    predictions_path.unlink(missing_ok=True)

    rows: list[dict[str, Any]] = []
    pooled: list[dict[str, Any]] = []

    for rung_name in rung_names:
        for scheme in schemes:
            all_examples: list[Example] = []
            all_predictions: list[set[str]] = []
            fit_s = predict_s = 0.0
            for fold in splits.folds(data, scheme):
                # A fresh model per fold. Re-fitting is the point of a fold; carrying one
                # model across them would leak the held-out group through its parameters.
                rung = models.build_rung(rung_name)
                preds, timing = models.fit_and_predict(rung, fold.train, fold.test)
                fit_s += timing.fit_s
                predict_s += timing.predict_s
                rows.append(
                    evaluate.fold_row(
                        scheme=scheme,
                        fold=fold.name,
                        rung=rung_name,
                        examples=list(fold.test),
                        predictions=preds,
                        timing=timing,
                    )
                )
                evaluate.write_predictions(
                    predictions_path,
                    list(fold.test),
                    preds,
                    scheme=scheme,
                    fold=fold.name,
                    rung=rung_name,
                )
                all_examples += list(fold.test)
                all_predictions += preds
                print(
                    f"  {rung_name:14} {scheme} {fold.name:26} "
                    f"n={len(fold.test):3}  fit={timing.fit_s:6.2f}s",
                    flush=True,
                )

            report = evaluate.score(
                all_examples, all_predictions, label=f"{rung_name}/{scheme}/pooled"
            )
            row: dict[str, Any] = {
                "rung": rung_name,
                "scheme": scheme,
                "n_folds": len(splits.folds(data, scheme)),
                "n_test": len(all_examples),
                "fit_s": round(fit_s, 3),
                "predict_s": round(predict_s, 3),
            }
            row.update(evaluate.headline(report))
            row.update(evaluate.exact_and_contested(all_examples, all_predictions))
            row["per_class_leakage"] = evaluate.per_class_leakage(all_examples, all_predictions)
            pooled.append(row)
            print(
                f"  {rung_name:14} {scheme} POOLED"
                f"  leak={_pct(row['leakage_underspecified'])}"
                f"  ret={_pct(row['retention_high'])}"
                f"  contrast={_pct(row['contrast_fidelity'])}"
                f"  exact={_pct(row['exact_set_match'])}",
                flush=True,
            )

    result = {
        "experiment": "E-15",
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "dataset": summarise(data),
        "coverage": {s: splits.coverage(data, s) for s in schemes},
        "folds": rows,
        "pooled": pooled,
    }
    (out_dir / "rows.jsonl").write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n", encoding="utf-8"
    )
    (out_dir / "results.json").write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    (out_dir / "report.md").write_text(to_markdown(result), encoding="utf-8")
    return result


def _pct(value: Any) -> str:
    return "  --  " if value is None else f"{float(value) * 100:5.1f}%"


# The committed prompted arms, read from E-14's artifacts rather than typed here, so this
# table cannot drift from the numbers the rest of the project quotes.
E14_RESULTS = Path("experiments/e14_validation/results")
REFERENCE_ARMS = (
    ("per-class-claude-sonnet-5.per-class-v1.s1", "per-class sonnet (prompted, best)"),
    ("baseline-gpt-4.1-mini.baseline-v2.s1", "baseline gpt (prompted, worst)"),
    ("read-only.s0", "read-only (floor)"),
    ("tool-ceiling.s0", "tool-ceiling (ceiling)"),
)


def reference_rows(root: Path | None = None) -> list[dict[str, Any]]:
    """The prompted arms, loaded from their committed reports. Never hardcoded."""
    root = root or E14_RESULTS
    out: list[dict[str, Any]] = []
    for stem, label in REFERENCE_ARMS:
        path = root / stem / "report.json"
        if not path.exists():
            continue
        report = json.loads(path.read_text(encoding="utf-8"))
        row = {"rung": label, "scheme": "S1-equivalent (E-14, heldout)"}
        row.update(evaluate.headline(report))
        out.append(row)
    return out


def to_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = [
        "# E-15 — the learned intent compiler",
        "",
        f"Generated {result['generated']} · Python {result['environment']['python']}",
        "",
        "Every rate below comes from `eval/scope_eval.py`, the same scorer that produced",
        "every prompted arm's numbers. Nothing in `agentfw/ml/` computes a rate of its own.",
        "",
        "## Dataset",
        "",
    ]
    ds = result["dataset"]
    lines += [
        f"- **{ds['n_examples']} examples**, {ds['n_distinct_texts']} textually distinct",
        f"- **{ds['n_classes']} effect classes**, {ds['mean_labels']} labels per example",
        f"- by split: {ds['by_split']}",
        f"- by world: {ds['by_world']}",
        f"- labels outside their own tool ceiling: {ds['labels_outside_tool_ceiling']}",
        "",
        "**Human ceiling for whole-effect-set exactness is 80%** (F-31: two blind labellers",
        "agreed 48/60). No figure here is read against 100%.",
        "",
        "## Prompted reference, from E-14's committed artifacts",
        "",
        "| arm | leakage | retention | contrast |",
        "|---|---|---|---|",
    ]
    for row in reference_rows():
        lines.append(
            f"| {row['rung']} | {_pct(row['leakage_underspecified'])} | "
            f"{_pct(row['retention_high'])} | {_pct(row['contrast_fidelity'])} |"
        )
    lines += [
        "",
        "## Learned rungs, pooled over each scheme's folds",
        "",
        "| rung | split | n | leakage | retention | contrast | exact-set "
        "| contested acc | fit s |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in result["pooled"]:
        lines.append(
            f"| {row['rung']} | {row['scheme']} | {row['n_test']} | "
            f"{_pct(row['leakage_underspecified'])} | {_pct(row['retention_high'])} | "
            f"{_pct(row['contrast_fidelity'])} | {_pct(row['exact_set_match'])} | "
            f"{_pct(row['contested_accuracy'])} | {row['fit_s']} |"
        )
    lines += [
        "",
        "## Per-fold rows",
        "",
        "| rung | split | fold | n | leakage | retention | contrast |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in result["folds"]:
        lines.append(
            f"| {row['rung']} | {row['scheme']} | {row['fold']} | {row['n_test']} | "
            f"{_pct(row['leakage_underspecified'])} | {_pct(row['retention_high'])} | "
            f"{_pct(row['contrast_fidelity'])} |"
        )
    return "\n".join(lines) + "\n"


def main(rungs: list[str], schemes: list[str], out: Path) -> dict[str, Any]:
    data = build()
    print(f"[E-15] {len(data)} examples, {len(data.classes)} classes")
    for scheme in schemes:
        print(f"[E-15] {json.dumps(splits.coverage(data, scheme))}")
    return run_grid(data, rungs, schemes, out)
