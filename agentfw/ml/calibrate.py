"""E-15c: select R3's decision rule inside the training split, then read held-out once.

**The hypothesis.** F-41 found that R3's leakage does not fall with data — 47.8% at n≈20 and
51.7% at n=86, flat across a fourfold increase — while its retention climbs steadily. Recall
improving while precision does not is the signature of a **decision rule placed wrongly**, not
of a model short of capacity or examples. E-15c asks whether that is what happened, because
E-15's R3 had its threshold (0.5) and its positive weighting (clamped at 50) fixed blind and
never validated.

**The one rule that makes this legitimate, enforced by the shape of this module.** Every
selection decision is made from **out-of-fold probabilities on the training split**, by grouped
cross-validation with the *scenario* as the group. `select()` never receives the held-out set
and has no argument through which it could. `evaluate_frozen()` reads held-out exactly once,
after `select()` has returned and its choice has been written to disk. There is no loop around
the pair, and adding one would be the failure this whole project is organised against (R-16).

**Grouped by scenario, not by example.** Variants of one scenario are minimal pairs sharing a
context sentence (D-010). A CV fold that split a triple would leak the answer into the
*selection*, which is a subtler and worse version of leaking it into the evaluation.

**Why per-class F1 for the thresholds and out-of-fold contrast for the weighting.** A threshold
is a per-class quantity and per-class F1 is the aligned per-class criterion; contrast fidelity
is a per-*scenario* metric and would be far too coarse to place nineteen cuts from 48 training
scenarios. The weighting is a single global choice, so it is selected on the metric the project
actually reports. Classes with no out-of-fold positive keep the default cut: inventing a
threshold for a class never observed positive is fitting noise.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from agentfw.ml import evaluate, models, splits
from agentfw.ml.dataset import Dataset, Example, build

# The registered search space. Written into E-15c before any fit; changing it after seeing a
# held-out number would be model selection against held-out wearing a different hat.
POS_WEIGHT_CAPS: tuple[float, ...] = (1.0, 5.0, 10.0, 50.0)
THRESHOLD_GRID: tuple[float, ...] = tuple(round(0.05 * i, 2) for i in range(1, 20))
N_FOLDS = 5


@dataclass
class Calibration:
    """The frozen decision rule, and enough provenance to audit how it was chosen."""

    pos_weight_cap: float
    thresholds: dict[str, float] = field(default_factory=dict)
    default_threshold: float = 0.5
    # Out-of-fold, training-only. Never a held-out number.
    oof_contrast: float | None = None
    oof_leakage: float | None = None
    oof_retention: float | None = None
    n_folds: int = N_FOLDS
    n_train: int = 0
    searched_caps: tuple[float, ...] = POS_WEIGHT_CAPS
    per_cap_oof_contrast: dict[str, float] = field(default_factory=dict)

    def apply_to(self, rung: Any) -> Any:
        rung.pos_weight_cap = self.pos_weight_cap
        rung.thresholds = dict(self.thresholds)
        rung.threshold = self.default_threshold
        return rung


def grouped_folds(train: Dataset, n_folds: int = N_FOLDS) -> list[tuple[Dataset, Dataset]]:
    """Deterministic k-fold over *scenarios*, so no triple is ever split.

    Scenarios are assigned round-robin over sorted ids rather than shuffled, because a fixed
    assignment is reproducible without carrying a seed and there is nothing to gain from
    randomising a partition that is used once.
    """
    scenario_ids = sorted({ex.scenario_id for ex in train})
    assignment = {sid: i % n_folds for i, sid in enumerate(scenario_ids)}
    out: list[tuple[Dataset, Dataset]] = []
    for k in range(n_folds):
        inner_train = [ex for ex in train if assignment[ex.scenario_id] != k]
        inner_val = [ex for ex in train if assignment[ex.scenario_id] == k]
        out.append((train.subset(inner_train), train.subset(inner_val)))
    return out


def oof_probabilities(
    train: Dataset, pos_weight_cap: float, n_folds: int = N_FOLDS
) -> tuple[list[Example], list[dict[str, float]]]:
    """Out-of-fold probabilities for every training example, at one weighting."""
    examples: list[Example] = []
    probabilities: list[dict[str, float]] = []
    for k, (inner_train, inner_val) in enumerate(grouped_folds(train, n_folds), start=1):
        rung = models.FineTunedEncoder(pos_weight_cap=pos_weight_cap)
        rung.fit(inner_train)
        probabilities += rung.predict_proba(list(inner_val))
        examples += list(inner_val)
        print(
            f"    cap={pos_weight_cap:>4}  fold {k}/{n_folds}  "
            f"train={len(inner_train):3} val={len(inner_val):3}",
            flush=True,
        )
    return examples, probabilities


def thresholds_from_oof(
    examples: Sequence[Example],
    probabilities: Sequence[dict[str, float]],
    classes: Sequence[str],
    default: float = 0.5,
) -> dict[str, float]:
    """Per-class cut maximising out-of-fold F1. Classes with no positive keep the default."""
    chosen: dict[str, float] = {}
    for klass in classes:
        truth = [klass in ex.labels for ex in examples]
        if not any(truth):
            chosen[klass] = default
            continue
        scores = [row.get(klass, 0.0) for row in probabilities]
        best_cut, best_f1 = default, -1.0
        for cut in THRESHOLD_GRID:
            tp = sum(1 for t, s in zip(truth, scores, strict=True) if t and s >= cut)
            fp = sum(1 for t, s in zip(truth, scores, strict=True) if not t and s >= cut)
            fn = sum(1 for t, s in zip(truth, scores, strict=True) if t and s < cut)
            f1 = (2 * tp) / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0
            # Ties go to the higher cut: of two rules that score the same on training data,
            # the more conservative one is the better bet under deny-by-default.
            if f1 >= best_f1:
                best_cut, best_f1 = cut, f1
        chosen[klass] = best_cut
    return chosen


def _decide(
    examples: Sequence[Example],
    probabilities: Sequence[dict[str, float]],
    thresholds: dict[str, float],
    default: float,
) -> list[set[str]]:
    out: list[set[str]] = []
    for row, ex in zip(probabilities, examples, strict=True):
        predicted = {c for c, p in row.items() if p >= thresholds.get(c, default)}
        out.append(predicted & set(ex.candidates))
    return out


def select(train: Dataset, n_folds: int = N_FOLDS) -> Calibration:
    """Choose the weighting and the thresholds. Training data only, by construction.

    This function has no held-out argument and never builds one. That is the guarantee, and
    it is checked by a test rather than promised in a docstring.
    """
    classes = train.classes
    best: Calibration | None = None
    per_cap: dict[str, float] = {}

    for cap in POS_WEIGHT_CAPS:
        examples, probabilities = oof_probabilities(train, cap, n_folds)
        thresholds = thresholds_from_oof(examples, probabilities, classes)
        predictions = _decide(examples, probabilities, thresholds, 0.5)
        report = evaluate.score(examples, predictions, label=f"oof-cap{cap}")
        head = evaluate.headline(report)
        contrast = head["contrast_fidelity"] or 0.0
        per_cap[str(cap)] = round(float(contrast), 4)
        print(
            f"  cap={cap:>4}  OOF contrast={contrast * 100:5.1f}%  "
            f"leak={_pct(head['leakage_underspecified'])}  "
            f"ret={_pct(head['retention_high'])}",
            flush=True,
        )
        candidate = Calibration(
            pos_weight_cap=cap,
            thresholds=thresholds,
            oof_contrast=round(float(contrast), 4),
            oof_leakage=head["leakage_underspecified"],
            oof_retention=head["retention_high"],
            n_folds=n_folds,
            n_train=len(train),
        )
        if best is None or (candidate.oof_contrast or 0) > (best.oof_contrast or 0):
            best = candidate

    assert best is not None
    best.per_cap_oof_contrast = per_cap
    return best


def _pct(value: Any) -> str:
    return "  --  " if value is None else f"{float(value) * 100:5.1f}%"


def evaluate_frozen(calibration: Calibration, out_dir: Path) -> dict[str, Any]:
    """Refit once on the full training split with the frozen rule, read held-out once.

    Called only after `select()` has returned and its choice has been written to disk. The
    result of this function may not change the calibration; if it is disappointing, that is
    the answer.
    """
    data = build()
    fold = splits.folds(data, "S1")[0]
    rung = calibration.apply_to(models.FineTunedEncoder())
    predictions, timing = models.fit_and_predict(rung, fold.train, fold.test)
    examples = list(fold.test)

    report = evaluate.score(examples, predictions, label="R3-calibrated")
    head = evaluate.headline(report)
    extra = evaluate.exact_and_contested(examples, predictions)

    artifact = out_dir / "armL-R3-calibrated.s1.jsonl"
    from agentfw.intent.store import CompiledScopeStore

    CompiledScopeStore.write(
        evaluate.scope_records(examples, predictions, label="armL-R3-calibrated"), artifact
    )

    return {
        "calibration": asdict(calibration),
        "heldout": {**head, **extra},
        "per_class_leakage": evaluate.per_class_leakage(examples, predictions),
        "fit_s": timing.fit_s,
        "predict_s": timing.predict_s,
        "artifact": str(artifact),
    }


def run(out_dir: Path | None = None, n_folds: int = N_FOLDS) -> dict[str, Any]:
    out_dir = out_dir or Path("experiments/e15_learned_compiler/results_calibration")
    out_dir.mkdir(parents=True, exist_ok=True)
    data = build()
    train = splits.folds(data, "S1")[0].train

    print(f"[E-15c] selecting on {len(train)} training examples, grouped {n_folds}-fold")
    calibration = select(train, n_folds)

    # Frozen *before* held-out is touched, and written to disk so the order is auditable.
    frozen_path = out_dir / "calibration.json"
    frozen_path.write_text(
        json.dumps(asdict(calibration), indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"[E-15c] FROZEN -> {frozen_path}")
    print(
        f"[E-15c] cap={calibration.pos_weight_cap}  "
        f"OOF contrast={_pct(calibration.oof_contrast)}  "
        f"thresholds spread "
        f"{min(calibration.thresholds.values()):.2f}-{max(calibration.thresholds.values()):.2f}"
    )

    print("[E-15c] refitting on the full training split and reading held-out ONCE")
    result = evaluate_frozen(calibration, out_dir)
    result["experiment"] = "E-15c"
    (out_dir / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    (out_dir / "report.md").write_text(to_markdown(result), encoding="utf-8")
    return result


def to_markdown(result: dict[str, Any]) -> str:
    cal = result["calibration"]
    held = result["heldout"]
    lines = [
        "# E-15c — calibrating R3 inside the training split",
        "",
        "Selection used **out-of-fold probabilities on the 86 training examples only**,",
        f"grouped {cal['n_folds']}-fold by scenario. Held-out was read **once**, after the",
        "configuration below was frozen and written to disk.",
        "",
        "## The frozen configuration",
        "",
        f"- **positive-weight cap: {cal['pos_weight_cap']}** "
        f"(searched {cal['searched_caps']}, E-15's blind value was 50.0)",
        f"- out-of-fold contrast fidelity: {_pct(cal['oof_contrast'])}",
        f"- out-of-fold leakage {_pct(cal['oof_leakage'])}, "
        f"retention {_pct(cal['oof_retention'])}",
        "",
        "| cap | OOF contrast |",
        "|---|---|",
    ]
    for cap, value in sorted(cal["per_cap_oof_contrast"].items(), key=lambda kv: float(kv[0])):
        lines.append(f"| {cap} | {_pct(value)} |")
    cuts = cal["thresholds"]
    lines += [
        "",
        "### Per-class thresholds",
        "",
        "| effect class | cut |",
        "|---|---|",
    ]
    for klass, cut in sorted(cuts.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| `{klass}` | {cut:.2f} |")
    lines += [
        "",
        "## Held-out, read once",
        "",
        "| | E-15 R3 (blind) | E-15c R3 (calibrated) |",
        "|---|---|---|",
        f"| leakage | 51.7% | **{_pct(held['leakage_underspecified'])}** |",
        f"| retention | 78.8% | **{_pct(held['retention_high'])}** |",
        f"| contrast fidelity | 25.8% | **{_pct(held['contrast_fidelity'])}** |",
        f"| exact-set match | 10.1% | {_pct(held['exact_set_match'])} |",
        "",
        "Reference: `per-class` sonnet 15.0% / 100% / 86.4%; R1 TF-IDF 1.7% / 45.5% / 39.4%.",
        "",
    ]
    return "\n".join(lines) + "\n"
