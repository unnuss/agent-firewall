"""E-15's four rungs, in cost order.

**Why a ladder rather than one model.** A single tuned number answers nothing: it cannot say
whether the win came from the representation, from the training, or from the label prior
being easy to hit. So each rung changes exactly one thing about the rung below it.

| rung | model | what it adds over the one above |
|---|---|---|
| R0 | label prior | nothing — it is the floor a metric must beat to mean anything |
| R1 | TF-IDF + one-vs-rest logistic regression | lexical features |
| R2 | frozen encoder embeddings + **the same** LR head | a semantic representation |
| R3 | fine-tuned encoder | task-specific training of that representation |

**R2 is the rung D-038 did not ask for and it is the one that makes the comparison readable.**
R1 against R3 changes representation *and* training together, so "the encoder won" would not
say which half won. R1 to R2 changes only the representation; R2 to R3 only the training.

**R0 is not filler either.** 3.10 of 19 classes are positive on average and three classes
(`READ:USER_FILES`, `READ:EMAIL`, `READ:CONTACTS`) dominate, so a model that predicts the
same three sets every time scores a respectable micro-F1. Reporting R0 is what stops that
number from being mistaken for skill.

**Every rung is masked to the tool ceiling.** A prediction is intersected with the effect
classes the scenario's registered tools could produce. That is the learned equivalent of
showing the prompted compiler its tool list, which it has always been shown (D-025), and it
costs at most one label in 293 (`dataset.py`).

**Heavy imports are local.** `torch` and `transformers` are imported inside the R2/R3 methods
so that `import agentfw.ml.models` works with the `ml` extra alone and a missing encoder
dependency produces a sentence instead of a traceback at module load.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from agentfw.ml.dataset import Dataset, Example

# Fixed everywhere a model can be seeded, so a rerun reproduces. E-13 established that seeds
# do not narrow a scenario-clustered interval, so seeds here are for reproducibility and not
# for a variance estimate; a rung that needs several is a rung reporting a mean, and this
# phase reports single deterministic fits.
SEED = 1


class Rung(Protocol):
    """What every rung must be, so `evaluate.py` never special-cases one."""

    name: str

    def fit(self, train: Dataset) -> None: ...

    def predict(self, examples: Sequence[Example]) -> list[set[str]]: ...


def _mask(prediction: set[str], example: Example) -> set[str]:
    """Intersect with what the tools could actually produce."""
    return prediction & set(example.candidates)


def _label_matrix(data: Dataset, classes: Sequence[str]):
    import numpy as np

    index = {c: i for i, c in enumerate(classes)}
    y = np.zeros((len(data), len(classes)), dtype=int)
    for row, ex in enumerate(data):
        for label in ex.labels:
            if label in index:
                y[row, index[label]] = 1
    return y


# ---------------------------------------------------------------------------
# R0 — the floor
# ---------------------------------------------------------------------------


@dataclass
class LabelPrior:
    """Predict every class that was positive in more than half the training rows.

    Deliberately the dullest possible model. It reads no word of the input; `predict` takes
    the example only to mask it to the tool ceiling, which is information the *scenario*
    supplies rather than the sentence. If a rung above cannot beat this, the metric being
    reported is measuring the label distribution rather than the model.
    """

    name: str = "R0-prior"
    threshold: float = 0.5
    always: set[str] = field(default_factory=set)

    def fit(self, train: Dataset) -> None:
        import collections

        counts = collections.Counter(c for ex in train for c in ex.labels)
        n = max(len(train), 1)
        self.always = {c for c, k in counts.items() if k / n > self.threshold}

    def predict(self, examples: Sequence[Example]) -> list[set[str]]:
        return [_mask(set(self.always), ex) for ex in examples]


# ---------------------------------------------------------------------------
# R1 — lexical
# ---------------------------------------------------------------------------


@dataclass
class TfidfLogReg:
    """TF-IDF over word n-grams, then one binary logistic regression per class.

    **One-vs-rest and not a joint model**, because with 293 examples a model that tries to
    learn label correlations has fewer examples per parameter than one that does not, and
    because the per-class decomposition is what makes the per-class leakage table in
    prediction 39 readable at all.

    `class_weight="balanced"` is on for a reason worth stating: the contested classes are the
    rare positives (`PURCHASE:FINANCIAL` is positive 10 times in 293) and they are the ones
    the whole project is about. Without it the classifier's best move on those columns is to
    predict zero always, which scores well and answers nothing.
    """

    name: str = "R1-tfidf"
    ngram_max: int = 2
    min_df: int = 1
    C: float = 1.0
    classes: tuple[str, ...] = ()

    def fit(self, train: Dataset) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.multiclass import OneVsRestClassifier

        self.classes = train.classes
        self._vec = TfidfVectorizer(
            ngram_range=(1, self.ngram_max),
            min_df=self.min_df,
            sublinear_tf=True,
            lowercase=True,
        )
        x = self._vec.fit_transform([ex.features() for ex in train])
        y = _label_matrix(train, self.classes)
        self._clf = OneVsRestClassifier(
            LogisticRegression(
                max_iter=2000, C=self.C, class_weight="balanced", random_state=SEED
            )
        ).fit(x, y)

    def predict(self, examples: Sequence[Example]) -> list[set[str]]:
        x = self._vec.transform([ex.features() for ex in examples])
        hits = self._clf.predict(x)
        out = []
        for row, ex in zip(hits, examples, strict=True):
            predicted = {c for c, on in zip(self.classes, row, strict=True) if on}
            out.append(_mask(predicted, ex))
        return out


# ---------------------------------------------------------------------------
# R2 / R3 — the encoder rungs
# ---------------------------------------------------------------------------

# Small on purpose. The question is whether a *cheap* model can do this; a 7B parameter
# encoder would answer a different and much less interesting question, and there is no GPU
# on this machine (PROJECT_STATE section 7).
ENCODER = "sentence-transformers/all-MiniLM-L6-v2"


@dataclass
class FrozenEncoderLogReg:
    """Mean-pooled embeddings from a frozen encoder, then R1's classifier head verbatim.

    The encoder's weights are never updated. That is the point: this rung differs from R1 in
    the representation and in nothing else, so the R1-to-R2 delta is attributable.
    """

    name: str = "R2-frozen"
    model_id: str = ENCODER
    C: float = 1.0
    classes: tuple[str, ...] = ()

    def _embed(self, texts: Sequence[str]):
        import torch
        from transformers import AutoModel, AutoTokenizer

        if not hasattr(self, "_tok"):
            self._tok = AutoTokenizer.from_pretrained(self.model_id)
            self._enc = AutoModel.from_pretrained(self.model_id)
            self._enc.eval()
        out = []
        with torch.no_grad():
            for start in range(0, len(texts), 32):
                batch = list(texts[start : start + 32])
                enc = self._tok(
                    batch, padding=True, truncation=True, max_length=128, return_tensors="pt"
                )
                hidden = self._enc(**enc).last_hidden_state
                mask = enc["attention_mask"].unsqueeze(-1).float()
                pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
                out.append(pooled)
            return torch.cat(out).numpy()

    def fit(self, train: Dataset) -> None:
        from sklearn.linear_model import LogisticRegression
        from sklearn.multiclass import OneVsRestClassifier

        self.classes = train.classes
        x = self._embed([ex.features() for ex in train])
        y = _label_matrix(train, self.classes)
        self._clf = OneVsRestClassifier(
            LogisticRegression(
                max_iter=2000, C=self.C, class_weight="balanced", random_state=SEED
            )
        ).fit(x, y)

    def predict(self, examples: Sequence[Example]) -> list[set[str]]:
        x = self._embed([ex.features() for ex in examples])
        hits = self._clf.predict(x)
        out = []
        for row, ex in zip(hits, examples, strict=True):
            predicted = {c for c, on in zip(self.classes, row, strict=True) if on}
            out.append(_mask(predicted, ex))
        return out


@dataclass
class FineTunedEncoder:
    """The same encoder, with a classification head, trained end to end.

    **This is the rung most likely to disappoint, and that is registered** (prediction 36).
    86 training examples on the primary split is far below what fine-tuning a transformer
    normally needs, and if it does not beat TF-IDF the finding is that the sample size and
    not the architecture is the binding constraint. Epochs and learning rate are fixed here
    rather than tuned: there is no validation set that is not also a test set, and tuning
    against the test set is the failure this whole project is organised against (R-16).

    **That reasoning was half right and E-15c is the correction.** It correctly forbids tuning
    against held-out; it does not excuse skipping cross-validation *inside the training split*,
    which touches nothing held out. `pos_weight_cap` and `thresholds` are the two knobs E-15c
    selects that way. Their defaults are E-15's blind values, so an unconfigured
    `FineTunedEncoder()` still reproduces E-15's published R3 numbers exactly and the original
    result stays regenerable.
    """

    name: str = "R3-finetuned"
    model_id: str = ENCODER
    epochs: int = 8
    lr: float = 3e-5
    batch_size: int = 16
    threshold: float = 0.5
    # E-15's blind clamp. E-15c searches {1, 5, 10, 50} by grouped CV on the training split.
    pos_weight_cap: float = 50.0
    # Per-class decision thresholds, class -> cut. Empty means "use `threshold` for every
    # class", which is E-15's condition.
    thresholds: dict[str, float] = field(default_factory=dict)
    classes: tuple[str, ...] = ()

    def fit(self, train: Dataset) -> None:
        import torch
        from torch.utils.data import DataLoader, TensorDataset
        from transformers import AutoModel, AutoTokenizer

        torch.manual_seed(SEED)
        self.classes = train.classes
        self._tok = AutoTokenizer.from_pretrained(self.model_id)
        self._enc = AutoModel.from_pretrained(self.model_id)
        hidden = self._enc.config.hidden_size
        self._head = torch.nn.Linear(hidden, len(self.classes))

        enc = self._tok(
            [ex.features() for ex in train],
            padding=True,
            truncation=True,
            max_length=128,
            return_tensors="pt",
        )
        y = torch.tensor(_label_matrix(train, self.classes), dtype=torch.float32)
        # Positive-class weighting, for the same reason R1 uses class_weight="balanced":
        # the rare classes are the interesting ones.
        pos = y.sum(0).clamp(min=1.0)
        pos_weight = ((len(train) - pos) / pos).clamp(max=self.pos_weight_cap)
        loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight)

        loader = DataLoader(
            TensorDataset(enc["input_ids"], enc["attention_mask"], y),
            batch_size=self.batch_size,
            shuffle=True,
            generator=torch.Generator().manual_seed(SEED),
        )
        params = list(self._enc.parameters()) + list(self._head.parameters())
        opt = torch.optim.AdamW(params, lr=self.lr)
        self._enc.train()
        for _ in range(self.epochs):
            for ids, mask, target in loader:
                opt.zero_grad()
                hidden_states = self._enc(input_ids=ids, attention_mask=mask).last_hidden_state
                m = mask.unsqueeze(-1).float()
                pooled = (hidden_states * m).sum(1) / m.sum(1).clamp(min=1e-9)
                loss = loss_fn(self._head(pooled), target)
                loss.backward()
                opt.step()
        self._enc.eval()

    def predict_proba(self, examples: Sequence[Example]) -> list[dict[str, float]]:
        """Per-class probabilities, which is what threshold calibration needs to exist.

        Separated from `predict` so that E-15c can select thresholds from *out-of-fold*
        probabilities on training data without ever asking the model for a decision.
        """
        import torch

        out: list[dict[str, float]] = []
        with torch.no_grad():
            for start in range(0, len(examples), 32):
                batch = list(examples[start : start + 32])
                enc = self._tok(
                    [ex.features() for ex in batch],
                    padding=True,
                    truncation=True,
                    max_length=128,
                    return_tensors="pt",
                )
                hidden = self._enc(**enc).last_hidden_state
                m = enc["attention_mask"].unsqueeze(-1).float()
                pooled = (hidden * m).sum(1) / m.sum(1).clamp(min=1e-9)
                probs = torch.sigmoid(self._head(pooled)).numpy()
                for row in probs:
                    out.append({c: float(p) for c, p in zip(self.classes, row, strict=True)})
        return out

    def cut_for(self, effect_class: str) -> float:
        """The cut for one class: `thresholds` wins, `threshold` is the fallback."""
        return self.thresholds.get(effect_class, self.threshold)

    def predict(self, examples: Sequence[Example]) -> list[set[str]]:
        return [
            _mask({c for c, p in row.items() if p >= self.cut_for(c)}, ex)
            for row, ex in zip(self.predict_proba(examples), examples, strict=True)
        ]


RUNGS: dict[str, type] = {
    "R0-prior": LabelPrior,
    "R1-tfidf": TfidfLogReg,
    "R2-frozen": FrozenEncoderLogReg,
    "R3-finetuned": FineTunedEncoder,
}

# The two that need only the `ml` extra. Used by the CLI to fail early with a useful
# sentence rather than at the first torch import inside a fold.
CHEAP_RUNGS = ("R0-prior", "R1-tfidf")


# What each rung needs, so a missing or unloadable extra becomes a sentence rather than a
# traceback from somewhere inside torch. R0 needs nothing beyond the core dependencies.
# Whole import *statements*, not module names, because `import transformers` succeeds lazily
# while `from transformers import AutoModel` is what actually fails when the stack is broken.
# Probing the shallow name reported a rung as available and then crashed inside the fit.
RUNG_REQUIRES: dict[str, tuple[str, ...]] = {
    "R0-prior": (),
    "R1-tfidf": ("from sklearn.linear_model import LogisticRegression",),
    "R2-frozen": (
        "from sklearn.linear_model import LogisticRegression",
        "from transformers import AutoModel",
    ),
    "R3-finetuned": (
        "from torch.utils.data import DataLoader",
        "from transformers import AutoModel",
    ),
}


def unavailable(rung_name: str) -> str | None:
    """Why this rung cannot run here, or None. Checked in a subprocess, and here is why.

    An ML package can be *installed* and still fail to load — a broken wheel, a missing
    system library, or an OS policy blocking one compiled DLL. Probing in-process would leave
    a half-initialised package in ``sys.modules``, which is how a numpy probe once took
    fifteen unrelated hypothesis property tests down with it. Asking a fresh interpreter costs
    one process start and has no side effects at all.
    """
    import subprocess
    import sys

    for statement in RUNG_REQUIRES.get(rung_name, ()):
        probe = subprocess.run(
            [sys.executable, "-c", statement], capture_output=True, text=True
        )
        if probe.returncode != 0:
            last = [ln for ln in probe.stderr.strip().splitlines() if ln.strip()]
            reason = last[-1] if last else "import failed"
            newline = chr(10)
            return (
                f"{rung_name} needs `{statement}`, which fails here:"
                f"{newline}  {reason}{newline}"
                f"Install the extra with `uv sync --extra ml` (R0/R1) or "
                f"`--extra ml-encoder` (R2/R3). If it is already installed, the package is "
                f"present but unloadable, which is an environment problem rather than a "
                f"missing dependency."
            )
    return None


def build_rung(name: str) -> Rung:
    try:
        return RUNGS[name]()  # type: ignore[return-value]
    except KeyError:
        raise SystemExit(f"unknown rung {name!r}; registered: {', '.join(RUNGS)}") from None


@dataclass
class Timing:
    fit_s: float = 0.0
    predict_s: float = 0.0


def fit_and_predict(rung: Rung, train: Dataset, test: Dataset) -> tuple[list[set[str]], Timing]:
    """Fit on train, predict on test, and time both. Prediction 41 needs the clock."""
    t0 = time.perf_counter()
    rung.fit(train)
    t1 = time.perf_counter()
    predictions = rung.predict(list(test))
    t2 = time.perf_counter()
    return predictions, Timing(fit_s=round(t1 - t0, 3), predict_s=round(t2 - t1, 3))
