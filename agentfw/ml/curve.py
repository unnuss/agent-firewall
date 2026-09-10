"""E-15b: how does the learned compiler scale with the number of training examples?

**What this is for.** E-15 left one question open that decides what anyone should do next.
F-37 says the binding constraint is *data* — the contested classes are the rarest positives in
the training set by construction, and the primary split trains on 86 examples. Prediction 36's
outcome says TF-IDF beat a fine-tuned transformer, which is what happens to a *starved* model
and equally what happens to a *misconfigured* one. A learning curve separates them.

**What it is not for, and this is registered.** No output of this module may select a
configuration, a rung, a training size, or an arm. E-15's numbers stand exactly as published.
The only thing a curve here is allowed to decide is what the *roadmap* says next. Held-out is
one-use-per-question, and a sizing measurement that quietly became a model-selection loop would
cost the project every S1 number it has.

**Subsampled by scenario, never by variant.** Variants of one scenario are minimal pairs
sharing a context sentence (D-010). Drawing variants independently would put two thirds of a
triple in train and the remaining third in test, and the resulting curve would measure how well
a model copies a sentence it has already seen.

**Repeated draws.** 86 examples is small enough that a single subsample is noise. Each fraction
is drawn several times with different seeds and the spread is reported, because a curve without
one cannot distinguish a slope from a wobble.
"""

from __future__ import annotations

import json
import random
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentfw.ml import evaluate, models, splits
from agentfw.ml.dataset import Dataset, build

# The registered grid. Fractions of the training split, and how many draws at each.
FRACTIONS: tuple[float, ...] = (0.25, 0.50, 0.75, 1.00)
DRAWS: dict[str, int] = {"R1-tfidf": 5, "R3-finetuned": 3}


@dataclass(frozen=True)
class CurvePoint:
    rung: str
    fraction: float
    n_scenarios: int
    n_examples: int
    seed: int
    contrast: float | None
    retention: float | None
    leakage: float | None
    exact: float


def subsample_by_scenario(train: Dataset, fraction: float, seed: int) -> Dataset:
    """Keep a random `fraction` of the training *scenarios*, with all their variants.

    At fraction 1.0 the original set is returned unchanged and no draw happens, so the last
    point of the curve is E-15's own S1 condition rather than a resample of it. Prediction 44
    checks that it reproduces E-15's published number.
    """
    if fraction >= 1.0:
        return train
    scenario_ids = sorted({ex.scenario_id for ex in train})
    keep_n = max(1, round(len(scenario_ids) * fraction))
    rng = random.Random(seed)
    keep = set(rng.sample(scenario_ids, keep_n))
    return train.subset(ex for ex in train if ex.scenario_id in keep)


def run(
    rung_names: list[str] | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    data = build()
    fold = splits.folds(data, "S1")[0]
    test = list(fold.test)
    rungs = rung_names or list(DRAWS)
    out_dir = out_dir or Path("experiments/e15_learned_compiler/results_curve")
    out_dir.mkdir(parents=True, exist_ok=True)

    points: list[CurvePoint] = []
    for rung_name in rungs:
        n_draws = DRAWS.get(rung_name, 3)
        for fraction in FRACTIONS:
            # At 1.0 every draw would be identical, so one is enough and saying so is
            # cheaper than pretending the spread means something.
            draws = 1 if fraction >= 1.0 else n_draws
            for seed in range(1, draws + 1):
                train = subsample_by_scenario(fold.train, fraction, seed)
                rung = models.build_rung(rung_name)
                predictions, _ = models.fit_and_predict(rung, train, fold.test)
                report = evaluate.score(
                    test, predictions, label=f"{rung_name}@{fraction:.2f}.s{seed}"
                )
                head = evaluate.headline(report)
                extra = evaluate.exact_and_contested(test, predictions)
                point = CurvePoint(
                    rung=rung_name,
                    fraction=fraction,
                    n_scenarios=len({ex.scenario_id for ex in train}),
                    n_examples=len(train),
                    seed=seed,
                    contrast=head["contrast_fidelity"],
                    retention=head["retention_high"],
                    leakage=head["leakage_underspecified"],
                    exact=extra["exact_set_match"],
                )
                points.append(point)
                print(
                    f"  {rung_name:14} {fraction:4.0%}  n={point.n_examples:3} "
                    f"({point.n_scenarios:2} scenarios)  seed {seed}  "
                    f"contrast={_pct(point.contrast)}  retention={_pct(point.retention)}",
                    flush=True,
                )

    summary = summarise(points)
    result = {
        "experiment": "E-15b",
        "note": (
            "Sizing measurement, not a hypothesis test about any arm. Nothing here selects a "
            "configuration, a rung, a training size or an arm; E-15's numbers stand."
        ),
        "fractions": list(FRACTIONS),
        "draws": DRAWS,
        "n_test": len(test),
        "points": [p.__dict__ for p in points],
        "summary": summary,
    }
    (out_dir / "curve.json").write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    (out_dir / "report.md").write_text(to_markdown(result), encoding="utf-8")
    return result


def _pct(value: Any) -> str:
    return "  --  " if value is None else f"{float(value) * 100:5.1f}%"


def summarise(points: list[CurvePoint]) -> dict[str, Any]:
    """Mean and spread per (rung, fraction), plus the segment prediction 42 is about."""
    out: dict[str, Any] = {}
    for rung in sorted({p.rung for p in points}):
        rows = []
        for fraction in FRACTIONS:
            sel = [p for p in points if p.rung == rung and p.fraction == fraction]
            if not sel:
                continue
            values = [p.contrast for p in sel if p.contrast is not None]
            rows.append(
                {
                    "fraction": fraction,
                    "n_examples": sel[0].n_examples,
                    "draws": len(sel),
                    "contrast_mean": round(statistics.fmean(values), 4) if values else None,
                    "contrast_min": round(min(values), 4) if values else None,
                    "contrast_max": round(max(values), 4) if values else None,
                    "retention_mean": round(
                        statistics.fmean([p.retention for p in sel if p.retention is not None]),
                        4,
                    ),
                }
            )
        last_gain = None
        if len(rows) >= 2 and rows[-1]["contrast_mean"] is not None:
            last_gain = round(rows[-1]["contrast_mean"] - rows[-2]["contrast_mean"], 4)
        out[rung] = {"rows": rows, "final_segment_gain": last_gain}
    return out


def to_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# E-15b — learning curve: is it the data or the model?",
        "",
        "**Sizing measurement, not a hypothesis test.** Nothing here selects a configuration,",
        "a rung, a training size or an arm. E-15's published numbers stand unchanged.",
        "",
        "Trained on nested subsamples of `dev` (86 examples, subsampled **by scenario**),",
        f"scored on the unchanged S1 test set ({result['n_test']} held-out variants).",
        "",
    ]
    for rung, block in result["summary"].items():
        lines += [
            f"## {rung}",
            "",
            "| train fraction | n examples | draws | contrast (mean) | min | max | retention |",
            "|---|---|---|---|---|---|---|",
        ]
        for row in block["rows"]:
            lines.append(
                f"| {row['fraction']:.0%} | {row['n_examples']} | {row['draws']} | "
                f"{_pct(row['contrast_mean'])} | {_pct(row['contrast_min'])} | "
                f"{_pct(row['contrast_max'])} | {_pct(row['retention_mean'])} |"
            )
        gain = block["final_segment_gain"]
        lines += [
            "",
            f"**75% → 100% gain: {_pct(gain)}** "
            f"({'still rising' if gain and gain >= 0.05 else 'flat or falling'})",
            "",
        ]
    return "\n".join(lines) + "\n"
