"""Tests for the learned intent compiler (Phase 6, E-15).

Three kinds of thing are asserted here, in descending order of how much they matter.

**The boundary.** D-038 promises the trusted path installs with `pydantic` and `pyyaml`
alone and that nothing under `agentfw/core/` touches ML. D-041 promises the learned model
cannot be trusted more than a prompted one. Those were paragraphs; here they are tests.

**The instrument.** The dataset and the splits decide every number this phase reports, so
they are asserted against the counts written into E-15's registration. If a label file
changes, these fail loudly rather than quietly re-basing the experiment.

**The leak that would invalidate everything.** Variants of one scenario are minimal pairs
(D-010) sharing a context sentence. A fold that puts two of them in train and one in test
leaks the answer, and the resulting number would look excellent and mean nothing.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from agentfw.ml import dataset as ds
from agentfw.ml import evaluate, models, splits

AGENTFW = Path(ds.__file__).resolve().parent.parent
CORE = AGENTFW / "core"
ML_PACKAGES = ("sklearn", "torch", "transformers", "numpy", "scipy")


_IMPORTABLE: dict[str, bool] = {}


def _importable(module: str) -> bool:
    """Can this module be imported — asked in a subprocess, so asking has no side effects.

    Two things forced this shape, and both are worth keeping.

    **`pytest.importorskip` catches only `ModuleNotFoundError`.** It does not cover a package
    that is *installed* but cannot load: a broken wheel, a missing system library, or — as
    happened on the dev machine — a Windows Application Control policy blocking one compiled
    DLL, which took `numpy.random` down and `sklearn` and `torch` with it. The `ml` extra is
    optional by D-038, so its tests must skip in that case rather than fail; a red suite would
    report the trusted path as broken when the trusted path is fine.

    **And the probe must not import anything into this process.** `hypothesis` seeds
    `numpy.random` when it detects numpy in `sys.modules`, so an in-process probe that pulled
    numpy in made all fifteen property tests in `test_core_*` fail on a DLL they never use.
    The subprocess keeps the test session numpy-free when the extra is unavailable, and costs
    one interpreter start per module asked about, once.
    """
    if module not in _IMPORTABLE:
        out = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            capture_output=True,
            text=True,
            cwd=AGENTFW.parent,
        )
        _IMPORTABLE[module] = out.returncode == 0
    return _IMPORTABLE[module]


needs_sklearn = pytest.mark.skipif(
    not _importable("sklearn"), reason="the `ml` extra is not loadable here"
)
needs_torch = pytest.mark.skipif(
    not _importable("torch.utils.data"), reason="the `ml-encoder` extra is not loadable here"
)


@pytest.fixture(scope="module")
def data() -> ds.Dataset:
    return ds.build()


# ---------------------------------------------------------------------------
# the boundary: D-038 and D-041, as assertions
# ---------------------------------------------------------------------------


def _imports(path: Path) -> list[str]:
    names: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def _trusted_modules() -> list[Path]:
    """The TCB plus the assembly that wires it. None of it may know ML exists."""
    return (
        sorted(CORE.glob("*.py"))
        + sorted((AGENTFW / "policy").glob("*.py"))
        + [AGENTFW / "firewall.py"]
    )


@pytest.mark.parametrize("path", _trusted_modules(), ids=lambda p: p.name)
def test_the_trusted_path_imports_no_ml(path: Path):
    """D-038: a reviewer must be able to verify this by reading, and now by running."""
    for name in _imports(path):
        root = name.split(".")[0]
        assert root not in ML_PACKAGES, f"{path.name} imports {name}"
        assert not name.startswith("agentfw.ml"), f"{path.name} imports {name}"


def test_the_tcb_still_installs_without_the_ml_extra():
    """`agentfw.core` must import in a process where the ML packages are unavailable.

    Run in a subprocess with the ML modules poisoned, because they are installed in this
    environment and a plain import would pass for the wrong reason.
    """
    script = f"""
import sys

BLOCKED = {ML_PACKAGES!r}


class Blocked:
    def find_module(self, name, path=None):
        if name.split(".")[0] in BLOCKED:
            raise ImportError("blocked: " + name)
        return None


sys.meta_path.insert(0, Blocked())
import agentfw.core.audit
import agentfw.core.effects
import agentfw.core.scope
import agentfw.firewall
import agentfw.policy.combinator

print("ok")
"""
    out = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, cwd=AGENTFW.parent
    )
    assert out.returncode == 0, out.stderr
    assert "ok" in out.stdout


def test_importing_the_models_module_does_not_pull_in_torch():
    """The heavy imports are inside the R2/R3 methods, so `ml` alone is enough for R0/R1."""
    script = (
        "import sys\n"
        "import agentfw.ml.models\n"
        "heavy = [m for m in ('torch', 'transformers') if m in sys.modules]\n"
        "print('heavy=' + ','.join(heavy))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, cwd=AGENTFW.parent
    )
    assert out.returncode == 0, out.stderr
    assert "heavy=" in out.stdout and out.stdout.strip().endswith("heavy=")


def test_no_ml_module_can_construct_a_structural_signal():
    """The invariant D-006 states and D-041 inherits, checked by reading the source.

    A learned component that could emit `Signal(structural=True)` would be grounds for a
    BLOCK the combinator trusts, which is exactly the thing the architecture forbids.

    Parsed rather than grepped. The first version of this test was a substring search and
    it failed on its own package docstring, which *describes* the prohibition — a fair
    warning that a text search here would also have missed `structural = True` and
    `structural=flag`. The AST sees a keyword argument or it sees nothing.
    """
    offenders: list[str] = []
    for path in sorted((AGENTFW / "ml").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg != "structural":
                    continue
                literal_false = (
                    isinstance(keyword.value, ast.Constant) and keyword.value.value is False
                )
                if not literal_false:
                    offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, f"structural= passed non-False in {offenders}"


# ---------------------------------------------------------------------------
# the instrument: counts E-15 registered
# ---------------------------------------------------------------------------


def test_the_dataset_matches_what_the_registration_says(data: ds.Dataset):
    summary = ds.summarise(data)
    assert summary["n_examples"] == 293
    assert summary["n_distinct_texts"] == 290
    assert summary["n_classes"] == 19
    assert summary["by_split"] == {"dev": 86, "heldout": 207}
    assert summary["labels_outside_tool_ceiling"] == 1


def test_building_the_dataset_is_deterministic(data: ds.Dataset):
    again = ds.build()
    assert [e.model_dump() for e in data] == [e.model_dump() for e in again]


def test_no_identifier_reaches_the_model(data: ds.Dataset):
    """CLAUDE.md: nothing may read a scenario id. `features()` is the only input."""
    for ex in data:
        features = ex.features()
        assert features == ex.text
        assert ex.scenario_id not in features
        assert ex.template not in features or ex.template == ds.HANDWRITTEN


def test_every_example_has_text_and_a_world(data: ds.Dataset):
    for ex in data:
        assert ex.text.strip()
        assert ex.world
        assert ex.split in ds.LABEL_FILES


# ---------------------------------------------------------------------------
# the leak that would invalidate everything
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scheme", ["S1", "S2", "S3"])
def test_no_fold_splits_a_scenario_across_train_and_test(data: ds.Dataset, scheme: str):
    """Variants of one scenario are minimal pairs; separating them leaks the answer."""
    for fold in splits.folds(data, scheme):
        train_ids = {ex.scenario_id for ex in fold.train}
        test_ids = {ex.scenario_id for ex in fold.test}
        overlap = train_ids & test_ids
        assert not overlap, f"{scheme}/{fold.name} splits scenario(s) {sorted(overlap)[:3]}"


@pytest.mark.parametrize("scheme", ["S1", "S2", "S3"])
def test_no_fold_is_empty(data: ds.Dataset, scheme: str):
    for fold in splits.folds(data, scheme):
        assert len(fold.train) > 0 and len(fold.test) > 0


def test_split_coverage_is_what_the_registration_claims(data: ds.Dataset):
    assert splits.coverage(data, "S1")["n_tested_distinct"] == 207
    assert splits.coverage(data, "S2")["n_tested_distinct"] == 293
    assert splits.coverage(data, "S2")["n_never_tested"] == 0
    assert splits.coverage(data, "S3")["n_tested_distinct"] == 192
    assert splits.coverage(data, "S3")["n_never_tested"] == 101


def test_leave_one_template_out_never_holds_out_handwritten(data: ds.Dataset):
    for fold in splits.folds(data, "S3"):
        assert fold.name != ds.HANDWRITTEN
        assert all(ex.template == fold.name for ex in fold.test)


# ---------------------------------------------------------------------------
# the models, on the cheap rungs only (R2/R3 need the ml-encoder extra)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", models.CHEAP_RUNGS)
def test_a_cheap_rung_never_predicts_outside_the_tool_ceiling(data: ds.Dataset, name: str):
    """The mask is the learned equivalent of showing the compiler its tool list."""
    if name != "R0-prior" and not _importable("sklearn"):
        pytest.skip("the `ml` extra is not loadable here")
    fold = splits.folds(data, "S1")[0]
    rung = models.build_rung(name)
    predictions, _ = models.fit_and_predict(rung, fold.train, fold.test)
    for ex, pred in zip(fold.test, predictions, strict=True):
        assert pred <= set(ex.candidates), f"{ex.scenario_id} predicted outside its tools"


def test_the_label_prior_reads_nothing_and_is_split_invariant(data: ds.Dataset):
    """R0 is the control. Its contrast fidelity is 0.0 on every split, by construction.

    If this ever varies by split, R0 has acquired an input it should not have and the
    "memorisation" reading of the S2/S3 gap loses its control.
    """
    seen = set()
    for scheme in ("S1", "S2", "S3"):
        examples: list[ds.Example] = []
        predictions: list[set[str]] = []
        for fold in splits.folds(data, scheme):
            rung = models.build_rung("R0-prior")
            preds, _ = models.fit_and_predict(rung, fold.train, fold.test)
            examples += list(fold.test)
            predictions += preds
        report = evaluate.score(examples, predictions, label=f"R0/{scheme}")
        seen.add(evaluate.headline(report)["contrast_fidelity"])
    assert seen == {0.0}


def test_an_unknown_rung_is_an_error():
    with pytest.raises(SystemExit):
        models.build_rung("R9-magic")


# ---------------------------------------------------------------------------
# the scorer is the project's own
# ---------------------------------------------------------------------------


@needs_sklearn
def test_scoring_goes_through_scope_eval_and_produces_its_shape(data: ds.Dataset):
    """A learned arm must be scored by the same code as a prompted one.

    Asserted by shape: the report carries scope_eval's own blocks. If someone later swaps
    in a bespoke metric, the keys change and this fails.
    """
    fold = splits.folds(data, "S1")[0]
    rung = models.build_rung("R1-tfidf")
    predictions, _ = models.fit_and_predict(rung, fold.train, fold.test)
    report = evaluate.score(list(fold.test), predictions, label="test")
    for block in ("contested", "by_slice", "ambiguity"):
        assert block in report
    contested = report["contested"]
    for key in (
        "leakage_underspecified_low",
        "leakage_explicit_low",
        "retention_high",
        "contrast_fidelity",
    ):
        assert key in contested


def test_a_prediction_becomes_a_real_compiled_scope(data: ds.Dataset):
    """Arm L's artifact must be the type `agentfw replay` already reads (D-041)."""
    example = data.examples[0]
    record = evaluate.as_compiled_scope(example, {"READ:EMAIL"}, label="R1-tfidf")
    assert record.scenario_id == example.scenario_id
    assert record.variant_id == example.variant_id
    assert record.utterance == example.text
    assert record.effects == ("READ:EMAIL",)
    # An empty prediction must stay empty rather than becoming an error, because under
    # deny-by-default an empty scope authorizes nothing and that is the safe direction.
    empty = evaluate.as_compiled_scope(example, set(), label="R1-tfidf")
    assert empty.effects == () and empty.error is None


# ---------------------------------------------------------------------------
# D-041 Arm H: the operation that cannot widen
# ---------------------------------------------------------------------------


def test_arm_h_can_only_withhold_never_add():
    """The whole safety argument for Arm H is that intersection cannot add a class.

    Checked on the committed artifact rather than on the operator, because what a replay
    reads is the file. If someone later replaces the intersection with a union or a
    "restore the class when the model is unsure" rule, this fails.
    """
    from agentfw.intent.store import CompiledScopeStore
    from agentfw.ml import arms

    assert arms.narrow is not None  # the operator under test lives here
    results = AGENTFW.parent / "experiments" / "e15_learned_compiler" / "results"
    arm_h_path = results / "armH-R1-tfidf-over-per-class.s1.jsonl"
    prompted_path = (
        AGENTFW.parent
        / "experiments"
        / "e14_validation"
        / "results"
        / "per-class-claude-sonnet-5.per-class-v1.s1.jsonl"
    )
    if not arm_h_path.exists():
        pytest.skip("Arm H artifact not built; run `agentfw learn` first")

    filtered = CompiledScopeStore.load(arm_h_path)
    prompted = CompiledScopeStore.load(prompted_path)
    for key, record in filtered.index.items():
        assert key in prompted.index, f"Arm H invented a variant: {key}"
        added = sorted(set(record.effects) - set(prompted.index[key].effects))
        assert not added, f"Arm H widened {key}: {added}"


def test_narrow_is_a_pure_intersection():
    """The unit-level version, so the property is tested without needing an artifact."""
    from agentfw.intent.compiler import CompiledScope
    from agentfw.ml.arms import narrow

    prompted = CompiledScope(
        scenario_id="s",
        variant_id="a",
        compiler="prompted",
        effects=("READ:EMAIL", "PURCHASE:FINANCIAL"),
    )
    # A prediction naming a class the prompted scope never granted must not introduce it.
    out = narrow(prompted, {"READ:EMAIL", "DELETE:CALENDAR"})
    assert set(out.effects) == {"READ:EMAIL"}
    assert any("PURCHASE:FINANCIAL" in q for q in out.open_questions)
    # Nothing withheld leaves the record alone.
    same = narrow(prompted, {"READ:EMAIL", "PURCHASE:FINANCIAL"})
    assert set(same.effects) == set(prompted.effects)


# ---------------------------------------------------------------------------
# E-15b: the learning curve's subsampler is the one place a leak could hide
# ---------------------------------------------------------------------------


def test_the_curve_subsamples_whole_scenarios_never_single_variants(data: ds.Dataset):
    """Drawing variants independently would split a minimal pair and leak the answer.

    The context sentence is shared across a scenario's variants (D-010), so a subsample that
    kept `a` and `b` but dropped `c` would let the model see two thirds of the triple it is
    about to be tested on. Checked at every registered fraction and seed.
    """
    from agentfw.ml import curve

    train = splits.folds(data, "S1")[0].train
    whole = {
        sid: {ex.variant_id for ex in train if ex.scenario_id == sid}
        for sid in {ex.scenario_id for ex in train}
    }
    for fraction in curve.FRACTIONS:
        for seed in range(1, 6):
            sub = curve.subsample_by_scenario(train, fraction, seed)
            kept: dict[str, set[str]] = {}
            for ex in sub:
                kept.setdefault(ex.scenario_id, set()).add(ex.variant_id)
            for sid, variants in kept.items():
                assert variants == whole[sid], (
                    f"fraction {fraction} seed {seed} kept a partial scenario {sid}: "
                    f"{sorted(variants)} of {sorted(whole[sid])}"
                )


def test_the_curve_is_deterministic_for_a_seed(data: ds.Dataset):
    from agentfw.ml import curve

    train = splits.folds(data, "S1")[0].train
    a = curve.subsample_by_scenario(train, 0.5, 7)
    b = curve.subsample_by_scenario(train, 0.5, 7)
    assert [e.scenario_id for e in a] == [e.scenario_id for e in b]


def test_the_full_fraction_returns_the_training_set_unchanged(data: ds.Dataset):
    """The curve's last point must be E-15's own S1 condition, not a resample of it."""
    from agentfw.ml import curve

    train = splits.folds(data, "S1")[0].train
    assert list(curve.subsample_by_scenario(train, 1.0, 1)) == list(train)


# ---------------------------------------------------------------------------
# E-15c: calibration must be selectable from training data alone
# ---------------------------------------------------------------------------


def test_select_has_no_way_to_see_heldout():
    """The R-16 guarantee, checked structurally rather than promised in a docstring.

    `select` takes the training split and a fold count. If someone later adds a `test=` or
    `heldout=` parameter, the selection could be tuned against the slice every S1 number in
    this repository is measured on, and this fails before that can ship.
    """
    import inspect

    from agentfw.ml import calibrate

    params = set(inspect.signature(calibrate.select).parameters)
    assert params == {"train", "n_folds"}, params
    forbidden = {"test", "heldout", "held_out", "eval", "evaluation", "target"}
    assert not (params & forbidden)


@pytest.mark.parametrize("n_folds", [3, 5])
def test_calibration_folds_never_split_a_scenario(data: ds.Dataset, n_folds: int):
    from agentfw.ml import calibrate

    train = splits.folds(data, "S1")[0].train
    seen: list[tuple[str, str]] = []
    for inner_train, inner_val in calibrate.grouped_folds(train, n_folds):
        overlap = {e.scenario_id for e in inner_train} & {e.scenario_id for e in inner_val}
        assert not overlap, f"CV fold splits scenario(s) {sorted(overlap)[:3]}"
        seen += [(e.scenario_id, e.variant_id) for e in inner_val]
    assert len(seen) == len(set(seen)) == len(train)


def test_a_class_never_seen_positive_keeps_the_default_threshold(data: ds.Dataset):
    """Fitting a cut for a class with no positive example is fitting noise."""
    from agentfw.ml import calibrate

    train = splits.folds(data, "S1")[0].train
    examples = list(train)
    # Every probability 0.9, but no example carries the invented class.
    probabilities = [{"NEVER:SEEN": 0.9} for _ in examples]
    chosen = calibrate.thresholds_from_oof(examples, probabilities, ["NEVER:SEEN"], default=0.5)
    assert chosen["NEVER:SEEN"] == 0.5


def test_threshold_search_separates_a_clean_signal(data: ds.Dataset):
    from agentfw.ml import calibrate

    train = splits.folds(data, "S1")[0].train
    klass = "READ:EMAIL"
    examples = [ex for ex in train if klass in ex.labels] + [
        ex for ex in train if klass not in ex.labels
    ]
    # Perfectly separable at 0.5: positives at 0.9, negatives at 0.1.
    probabilities = [{klass: 0.9 if klass in ex.labels else 0.1} for ex in examples]
    cut = calibrate.thresholds_from_oof(examples, probabilities, [klass])[klass]
    assert 0.1 < cut <= 0.9


def test_the_frozen_calibration_actually_reconfigures_the_rung():
    from agentfw.ml import calibrate

    cal = calibrate.Calibration(pos_weight_cap=5.0, thresholds={"READ:EMAIL": 0.35})
    rung = cal.apply_to(models.build_rung("R3-finetuned"))
    assert rung.pos_weight_cap == 5.0
    assert rung.cut_for("READ:EMAIL") == 0.35
    assert rung.cut_for("PURCHASE:FINANCIAL") == 0.5  # falls back to the default


def test_an_unconfigured_r3_still_reproduces_e15s_condition():
    """E-15's published R3 must stay regenerable after E-15c added the knobs."""
    rung = models.build_rung("R3-finetuned")
    assert rung.pos_weight_cap == 50.0
    assert rung.thresholds == {}
    assert rung.threshold == 0.5
