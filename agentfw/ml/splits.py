"""The three splits E-15 registered, and the measurement that chose them.

**Why there are three and not one.** D-038 asked for leave-one-world-out, "because
surface-form memorisation is the live risk". Measured against the templates, LOWO does not
test for that risk at all. The 60 underspecified template instances draw their asking clause
from **22 distinct strings**, and those strings are reused across worlds:
`"Can you deal with that?"` appears in 6 instances spanning 5 templates and 5 different
contested classes. A model tested on `lab_heldout` under LOWO has therefore already seen the
test sentence's ask clause while training on `office_heldout`.

The split that isolates memorisation is **leave-one-template-out**: a held-out template brings
an unseen phrasing pool *and* an unseen contested class. LOWO is kept anyway, because the gap
between the two is E-15's prediction 35 and is a fact about the benchmark rather than about
any model — it tells whoever evaluates on this data next which split to believe.

**S1 is the primary** because it is how every other experiment in this project is split:
train on `dev`, test on `heldout`. It has a second virtue nobody designed for. `dev` is 48
scenarios, **all hand-written**; `heldout` is 81, of which 66 come from 11 templates. So S1 is
also a hand-written-to-generated distribution shift, which is a harder and more honest test
than a random partition of one pool would be.

**No split is random.** Every fold here is defined by a group — a file, a world, a template —
and never by a shuffle. Three variants of one scenario are minimal pairs of each other
(D-010); putting two of them in train and one in test would leak the answer through the
context sentence they share, and would produce a number that means nothing.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from agentfw.ml.dataset import HANDWRITTEN, Dataset, Example


@dataclass(frozen=True)
class Fold:
    """One train/test partition, named so it can be a row in a table."""

    scheme: str  # "S1" | "S2" | "S3"
    name: str  # which group was held out
    train: Dataset
    test: Dataset

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return (
            f"Fold({self.scheme}/{self.name}: {len(self.train)} train, {len(self.test)} test)"
        )


def _partition(data: Dataset, key, held_out, scheme: str, name: str) -> Fold:
    train = [ex for ex in data if key(ex) != held_out]
    test = [ex for ex in data if key(ex) == held_out]
    return Fold(scheme=scheme, name=name, train=data.subset(train), test=data.subset(test))


def s1_dev_to_heldout(data: Dataset) -> Fold:
    """The primary split: train on the hand-written dev labels, test on the held-out ones."""
    return Fold(
        scheme="S1",
        name="dev->heldout",
        train=data.subset(ex for ex in data if ex.split == "dev"),
        test=data.subset(ex for ex in data if ex.split == "heldout"),
    )


def s2_leave_one_world_out(data: Dataset) -> Iterator[Fold]:
    """Four folds, one per world fixture.

    Expected — and registered as prediction 35 — to look *better* than S3, because the ask
    phrasings cross worlds. A small S2/S3 gap would be the surprising outcome.
    """
    for world in sorted({ex.world for ex in data}):
        yield _partition(data, lambda ex: ex.world, world, "S2", world)


def s3_leave_one_template_out(data: Dataset) -> Iterator[Fold]:
    """One fold per template. Hand-written scenarios are always in train, never a fold.

    A hand-written scenario has no template and therefore no phrasing pool to hold out;
    grouping them all into a twelfth "handwritten" fold would hold out 101 examples at once
    and measure something else entirely. They stay in train, which is also the deployment
    story: a template is the thing that would be new.
    """
    for template in sorted({ex.template for ex in data} - {HANDWRITTEN}):
        yield _partition(data, lambda ex: ex.template, template, "S3", template)


def s4_leave_one_ask_phrase_out(data: Dataset) -> Iterator[Fold]:
    """One fold per asking clause. **Post-hoc and unregistered** — a diagnostic, not a result.

    Added after S2 and S3 were run, because their gap turned out to have two explanations
    rather than the one prediction 35 named. Holding out a template removes that template's
    phrasings *and*, since **eight of the nine contested classes have a sole template
    source**, nearly all of that class's positive training examples. So a low S3 number is
    consistent with memorisation and equally consistent with the model simply never having
    seen the class.

    Holding out a *phrase* separates them: the contested class survives in training, because
    the other instances of the same template use other phrases, while the exact test wording
    does not. If S4 lands near S2 the gap was class coverage; if it lands near S3 it was
    phrasing. Either answer is worth having and neither was registered, so it is reported as
    a diagnostic and labelled as one wherever it appears.

    Scenarios with no ask phrase (the 113 hand-written and non-`af_auth` ones) are always in
    train, exactly as hand-written scenarios are under S3.
    """
    for phrase in sorted({ex.ask_phrase for ex in data if ex.ask_phrase}):
        yield _partition(data, lambda ex: ex.ask_phrase, phrase, "S4", phrase)


SCHEMES: dict[str, str] = {
    "S1": "train on dev (hand-written), test on held-out",
    "S2": "leave one world out (4 folds)",
    "S3": "leave one template out (11 folds)",
    "S4": "leave one ask phrase out (post-hoc diagnostic, unregistered)",
}


def folds(data: Dataset, scheme: str) -> list[Fold]:
    if scheme == "S1":
        return [s1_dev_to_heldout(data)]
    if scheme == "S2":
        return list(s2_leave_one_world_out(data))
    if scheme == "S3":
        return list(s3_leave_one_template_out(data))
    if scheme == "S4":
        return list(s4_leave_one_ask_phrase_out(data))
    raise ValueError(f"unknown split scheme {scheme!r}; registered: {sorted(SCHEMES)}")


def coverage(data: Dataset, scheme: str) -> dict[str, object]:
    """How much of the dataset a scheme actually scores, and whether it scores it once.

    S1 tests 207 of 293 exactly once. S2 tests all 293 exactly once across its folds. S3
    tests only the 192 template-generated examples, and the 101 hand-written ones are never
    in a test set at all. That asymmetry is real and is why the three numbers are never
    pooled into one headline.
    """
    tested: list[Example] = []
    for fold in folds(data, scheme):
        tested += list(fold.test)
    keys = [(ex.scenario_id, ex.variant_id) for ex in tested]
    return {
        "scheme": scheme,
        "description": SCHEMES[scheme],
        "n_folds": len(folds(data, scheme)),
        "n_tested": len(keys),
        "n_tested_distinct": len(set(keys)),
        "n_never_tested": len(data) - len(set(keys)),
    }
