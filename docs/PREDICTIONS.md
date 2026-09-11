# Registered predictions — the full ledger

**48 predictions, written down before the runs that decided them. 14 were falsified and
published.** This file is the index; each row links to the experiment that registered it and the
section that scored it, both in [`EXPERIMENTS.md`](EXPERIMENTS.md).

The discipline is the point. A prediction registered *after* a result is a description; one
registered before it is a test that can fail. Roughly **29% of these failed**, which is the only
reason the other 71% are worth reading.

| | count |
|---|---|
| **held** | 32 |
| **falsified or failed** | 14 |
| partial / split | 2 |
| **total** | **48** |

---

## A numbering collision this consolidation found, and did not silently fix

**There are two prediction numbering schemes in this repository and they overlap.**

* The **global scheme, 1–48**, is the one this ledger tracks and the one `PROJECT_STATE.md`
  summarises. It begins at E-00g and runs forward.
* **E-09a, E-01b and E-10 each used their own local `1..N` numbering**, registered before the
  global scheme settled. So *"prediction 3"* means E-09a's third prediction in one section of
  `EXPERIMENTS.md` and E-00g's third in another.

They are **not renumbered here.** Renumbering would silently invalidate every cross-reference in
`DECISIONS.md`, `EXPERIMENTS.md` and the commit history, which is a worse outcome than an
ambiguity that is written down. The rule for reading the repository: **a bare prediction number
is only meaningful inside its own experiment's section.** The local sets are listed at the
bottom.

A second gap worth recording: `PROJECT_STATE.md`'s summary table **omitted predictions 17–22**
(E-12's) entirely. They are scored below.

---

## The global ledger

### E-00g — the dev baseline, re-measured after the benchmark repair

| # | Prediction | Outcome |
|---|---|---|
| 1 | competency gate passes; compliance rises above 81.2% | **held** |
| 2 | underspecified overreach above 30%, CI overlapping 38.9% | **held** |
| 3 | explicit-low overreach under 5% | **held** |
| 4 | the authority gap exceeds +25 pp | **held** |
| 5 | benign BTC rises | **held** |

*All five held. The dev phenomenon survived its own instrument being fixed, and grew (D-018).*

### E-00i — the first held-out baseline (n=11) · **superseded by E-00j**

| # | Prediction | Outcome |
|---|---|---|
| 6 | competency gate passes (≥ 0.60) | **held** |
| 7 | underspecified overreach above 25% | **held, and far above** — 81.8% |
| 8 | explicit-low overreach under 10% | **held** |
| 9 | overreach incidence ≥ 50% of triples | **held** |

*All four held — **and the slice was too small.** Prediction 7's 81.8% came in at 49.4% on 60
triples. Holding a prediction on an underpowered sample is not evidence; this block is the
cautionary example in the repository and is why E-00j exists.*

### E-11 — the held-out validation, and the exit criterion on D-032

| # | Prediction | Outcome |
|---|---|---|
| 10 | `per-class` on gpt-4.1-mini leaks **under 15%** | **FALSIFIED** |
| 11 | `baseline` leaks at least 20 pp more than `per-class` | **failed** |
| 12 | `baseline` on Sonnet leaks less than on gpt-4.1-mini | **held** |
| 13 | some compiled arm reaches **0.0% overreach and 0.0% ASR** | **FALSIFIED** |
| 14 | best compiled arm's compliance within 10 pp of gold | **held** — for the wrong reason, then for the right one after the F-29 repair |
| 15 | `tool-ceiling` reproduces undefended overreach | **held** — the initial "failed" was an instrument artifact |
| 16 | `per-class` costs retention on gpt-4.1-mini and not on Sonnet | **held** |

*10 and 13 were the **registered exit criterion**, and both failed. That is what reopened D-032
and produced D-034 — a conclusion withdrawn on evidence rather than renegotiated.*

### E-12 — can a grant be refused by the compiler's own doubt?

| # | Prediction | Outcome |
|---|---|---|
| 17 | R2 takes `per-class` gpt held-out leakage **below 15%** | **held** |
| 18 | R2 cuts `baseline` gpt held-out leakage by **≥ 10 pp** | **failed**, by 0.9 pp |
| 19 | R2 costs **under 10 pp of retention** on every arm | **failed** on three of four |
| 20 | R2 cuts `baseline` gpt *dev* leakage by ≥ 20 pp | **failed**, by 2.2 pp |
| 21 | some arm reaches **0.0% overreach** held out | **failed** |
| 22 | R1 does markedly less than R2 | **partly held** |

*Four of six failed, including prediction 20 — which was registered as **the anti-fitting
guard**: if the rule only worked where it was developed, it had been fitted to that slice. The
guard fired. The coupling rule was measured twice and **never adopted** (D-035).*

### E-00j — the undefended baseline rebuilt at N=60

| # | Prediction | Outcome |
|---|---|---|
| 23 | competency gate passes | **held** |
| 24 | underspecified overreach **below** 81.8%, landing in 45–70% | **held** — 49.4% |
| 25 | explicit-low under 10% | **held** |
| 26 | incidence ≥ 50% of triples | **held** |
| 27 | the three worlds differ by < 20 pp | **held** |
| 28 | the least consequential classes do not overreach > 15 pp below the most | **held** |

*Prediction 24 is the project correcting its own headline **in advance**: it predicted its
earlier 81.8% was wrong before measuring. Prediction 28 is the first real test of D-018's claim
that ambiguity rather than consequence size drives the failure.*

### E-14 — the 2×2 re-run at N=60

| # | Prediction | Outcome |
|---|---|---|
| 29 | the 2×2 ordering holds: `baseline` gpt worst, `per-class` Sonnet best | **held** |
| 30 | **no compiled arm reaches 0.0%** at the verdict level | **held** |
| 31 | `per-class` gpt leaks 15% or more | **held**, narrowly |
| 32 | ASR 0.0% under every compiled scope, undefended above 15% | **held**, weakly — 5 injection scenarios it had seen |
| 33 | the best arm's interval is narrower than ±12 pp | **held** |
| 34 | `tool-ceiling` reproduces undefended overreach within 5 pp | **held**, exactly |

*Prediction 30 was the registered criterion on D-034, and it decided D-037: the band is real on
adequate power.*

### E-15 — the learned intent compiler

| # | Prediction | Outcome |
|---|---|---|
| 35 | S2 exceeds S3 by ≥ 15 pp for the best rung | **held** — 40.9 pp at R1, 33.4 pp at R3. **The stated reason was wrong**; see F-36 |
| 36 | R1 within 10 pp of R3 on S1 contrast | **falsified in letter, held in spirit, split-dependent.** R1 is 13.6 pp *above* R3 on S1 and 19.7 pp *below* on S3 |
| 37 | contested accuracy ≥ 85% **and** exact-set ≤ 40% | **split.** Exact-set 26.6% ✓; contested accuracy 79.2% ✗ |
| 38 | no learned rung reaches 0.0% leakage on S1 | **falsified on a technicality.** R0 reaches it at 0.0% retention; no rung that grants meaningfully does |
| 39 | `WRITE:USER_FILES` among the three worst by leakage | **falsified, unfavourably.** It leaks 0.0% *and* retains 0.0% — never predicted (F-40) |
| 40 | Arm H cuts leakage ≥ 3 pp for ≤ 5 pp of retention | **falsified.** −15 pp leakage for **−54.5 pp** retention (F-39) |
| 41 | Arm L compiles 207 utterances in < 60 s on CPU for < $0.01 | **held** — 6.13 s, $0.00 |

*Four of seven falsified, in the phase that exists to showcase machine learning. All four were
published.*

### E-15b — the learning curve (sizing, not a hypothesis test)

| # | Prediction | Outcome |
|---|---|---|
| 42 | R3 still rising at the largest size, ≥ 5 pp over the final segment | **held** — +9.1 pp |
| 43 | R1 saturates earlier than R3 | **held, but barely and misleadingly** — 7.3 pp vs 9.1 pp, and *neither* saturates |
| 44 | neither rung reaches 86.4%; the endpoint reproduces E-15 | **held**, both halves |

*All three held — weaker evidence than it looks, because a curve's shape is easier to predict
than a system's behaviour.*

### E-15c — does calibration rescue the fine-tuned encoder?

| # | Prediction | Outcome |
|---|---|---|
| 45 | calibration at least halves scope-level leakage, to below 25% | **falsified as written** — 31.7%. The criterion was also in the wrong currency; the verdict-level analogue nearly halves |
| 46 | calibrated contrast reaches ≥ 39.4% | **falsified** — 13.6%, worse than the blind configuration |
| 47 | still below `per-class`'s 86.4% contrast | **held** |
| 48 | the selected weight cap is below 50 | **falsified, decisively.** CV chose **50.0** — the blind value. The weighting was never misconfigured |

*Prediction 48 is the most informative failure in the ledger: it refuted the hypothesis the
experiment was built to confirm.*

---

## The local prediction sets, not folded into the global scheme

Listed for completeness. Their numbers collide with the global ledger above and must be read
inside their own sections of [`EXPERIMENTS.md`](EXPERIMENTS.md).

| experiment | local predictions | summary of outcomes |
|---|---|---|
| **E-09a** — the compiler against the gold scopes | 1–6 | Mixed. Local 1 held (exact match under 50%); **local 3 FALSIFIED** — the registered arm licensed the contested class on 53.3% of underspecified instructions, *worse* than the undefended agent, which is F-16 and the finding Phase 3 was built on |
| **E-01b** — the compiled replay | 1–4 (local) | Scored in the E-01b result section |
| **E-10** — can the compiler's authority prior be changed? | 1–6, plus 7–10 for arm 4 | Local 1 "half falsified"; local 4 **falsified and inverted** (10.0%, five times lower on the other model, F-18); local 5 and 6 falsified — `per-class` reached 0.0%. Arm 4's 7–9 held |

---

## What a reader should take from this ledger

1. **Registration is not decoration here.** The exit criterion on Phase 3's central conclusion
   (predictions 10 and 13) failed, and the conclusion was withdrawn rather than the criterion
   renegotiated (D-034).
2. **An anti-fitting guard fired and the feature was dropped.** Prediction 20 existed to detect a
   rule fitted to its development slice. It failed, and the coupling rule was never adopted
   (D-035).
3. **A prediction holding is not always good news.** E-00i's four held on 11 triples; one of them
   was wrong by 32 points. Power matters more than direction.
4. **A prediction failing is sometimes the best outcome available.** Prediction 48 refuted the
   hypothesis its own experiment was designed to confirm, which closed the question faster than
   confirming it would have.
