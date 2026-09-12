# PROJECT STATE

**Read this first.** It is the handoff document between development sessions.

**Last updated:** 2026-09-09 · **Phase 6 complete — the first ML in the project, built,
measured and _not adopted_ under its own registered rule (D-042).** Four of seven registered
predictions were falsified. The result that matters is methodological: the learned compiler
looks hopeless at the **scope** level (45.5% retention vs 100%) and is nearly as good as gold
at the **verdict** level (1.7% contested executed vs `per-class`'s 5.6%, 81.3% task completion
vs 82.8%), because a wrongly *dropped* class becomes an ASK and a wrongly *granted* one is
silent. **F-14 with the sign reversed (F-38).** A follow-up sizing run (**E-15b**) then found
**both** learned rungs are still data-starved at 86 examples — and that only TF-IDF is learning
to *discriminate*: its leakage stays near zero while retention climbs, whereas the fine-tuned
encoder's leakage sits flat at ~50% across a fourfold data increase, so more data would push it
toward `tool-ceiling` rather than toward gold (**F-41**). **E-15c then ran the calibration
experiment F-41 points at and settled it: calibration materially *improves* R3 at the verdict
level (contested executed 27.8% → 16.1%) and makes it *worse* at the scope level (contrast 25.8%
→ 13.6%), and leaves it roughly ten times worse than TF-IDF on the security axis. Three of four
predictions falsified, including the decisive one — cross-validation chose E-15's blind weight
cap, so the weighting was never misconfigured. Phase 6's conclusion now stands _by evidence_
(F-42, F-43).** Spend: **$0**. · **Phase 5.5 complete.** `uv run agentfw demo` replays four
committed episodes through the real monitor and prints ALLOW / ASK → APPROVED / ASK → DENIED /
BLOCK, with no API key and no network; `LICENSE` exists (MIT, D-040); the README has runnable
commands where it had none. The repo is now presentable from here onward, which was the point
of doing it before the substance. · **Phase 5 (2026-09-08) confirmed D-034 on adequate power
(D-037)** at N=60 across three worlds with blind-authored gold scopes. · **Next: Phase 7 —
presentation (restructure the README, move the phase-by-phase narrative to
`docs/RESEARCH_LOG.md`), then Phase 8 defensibility and the post. Phase 4's cost model is
still deferred, and D-042 gives it a new reason to exist. The whole plan is in
`docs/ROADMAP.md`.**

---

## 0. Where the authoritative account lives (new in Phase 6.9)

**This file is a handoff document, not a reference.** For what the project concluded, read these
instead — they were written in Phase 6.9 precisely so that the truth stops being distributed
across a 4,700-line experiment log and this file:

| | |
|---|---|
| [`docs/RESULTS.md`](docs/RESULTS.md) | **The canonical numbers.** Every table **generated** from committed artifacts by `agentfw results`. Where it disagrees with anything else, including this file, it wins |
| [`docs/PREDICTIONS.md`](docs/PREDICTIONS.md) | All 48 registered predictions with outcomes — **32 held, 14 falsified, 2 partial** |
| [`docs/FINDINGS.md`](docs/FINDINGS.md) | All 43 findings, each marked live / fixed / superseded / narrowed / open |
| [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) | Everything the project does not establish, ordered by how much it should change your reading |
| [`docs/RESEARCH_LOG.md`](docs/RESEARCH_LOG.md) | The phase narrative, moved verbatim out of `README.md` |

**Two record-keeping defects Phase 6.9 found and did not silently fix.** There are **two
overlapping prediction numbering schemes** — E-09a, E-01b and E-10 used local `1..N` numbering
that collides with the global 1–48 — so a bare prediction number is only meaningful inside its
own experiment's section. And this file's own summary table **omitted predictions 17–22**
entirely. Both are documented in `PREDICTIONS.md`; neither was renumbered, because renumbering
would invalidate every cross-reference in the repository.

## 0b. If you are the next session, do exactly this

0. Run it before you read anything: `uv run agentfw demo`. Three seconds, no key, and it is
   the shortest statement of what this project does. Then `uv run agentfw demo --scope
   tool-ceiling` for the same four scenes under the ablation where the defense does nothing.
1. **Phase 6 first, if you are picking up from here.** Read **E-15's registration** in
   `docs/EXPERIMENTS.md` (written before any model was fitted), then **E-15's result**, then
   **D-042** (why it was not adopted and why the rule that rejected it was itself the wrong
   instrument) and **D-041** (where a learned model is allowed to sit). Then findings
   **F-36 → F-43**. Two outlive the phase. **F-36**: leave-one-world-out overstates
   generalisation on this benchmark by 35–41 pp. **F-42**: four unrelated interventions have now
   lowered leakage here and **all four did it by granting less**, so treat any leakage
   improvement as paid for in retention until the contrast number is shown. Then read
   **E-15c's result** for the two criticisms it makes of its own design — one of them is that
   it registered its criterion in the currency D-042 had disqualified one experiment earlier.
2. Read `CLAUDE.md`, then this file, then **`docs/DECISIONS.md` D-037** — it is the verdict on
   the whole Phase 3.5/Phase 5 arc and it says what Phase 4 inherits. Then **D-034** (what was
   reopened), **D-036** (why Phase 5 ran before Phase 4), **D-035** (the coupling rule, still
   not adopted), **D-033** (how the held-out labels were authored), and **D-032** (reopened;
   read it for the argument, D-037 for its status).
3. Read findings **F-32 → F-33 → F-34** in `docs/EXPERIMENTS.md`, in that order. F-32 says the
   contested effect class explains six times more variance than the domain; F-33 says the
   residual is six utterances and not a rate; F-34 says the two prompt formulations differ in
   what they can *express*, not only in how well they guess. Reading any one alone overstates
   it.
4. **Then** read **F-16 → F-17 → F-18 → F-19** for Phase 3's argument on the dev slice — but
   read them knowing F-19's "substitutes" reading did not survive N=60, and the interaction is
   still unresolved (E-14, last paragraph).
5. Read **F-29** before quoting any compliance number, and **F-35** before quoting `read-only`
   as a floor.
6. **The apparatus boundary is real.** Every number from E-00, E-00b, E-00f, E-00h, E-01a and
   E-01b is **pre-repair**; everything from E-00g onward is **post-repair**. A `CONTRACT.md`
   sits in each pre-repair result directory. Never difference across it.

Health check (~6 min measured on the dev machine, no API calls, no keys needed):

```bash
.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m agentfw.cli validate
```

Expect **575 passed**. If the `ml` extra will not import, two of them skip instead — see
section 7. The four gold-scope tests that were red on purpose through
Phase 5's authoring step are green: the labels exist now. Any failure is a real one. `validate`
reports 24 AF-Auth / 6 AF-Inject / 18 benign **dev** scenarios and **66 AF-Auth / 5 AF-Inject /
10 benign held-out**, 23 tools.

Five commands reproduce with no key and no money:

```bash
.venv/Scripts/python.exe -m agentfw.cli demo
.venv/Scripts/python.exe -m agentfw.cli probe-contract
.venv/Scripts/python.exe -m agentfw.cli replay experiments/e01b_compiled/config.yaml
.venv/Scripts/python.exe -m agentfw.cli replay experiments/e14_validation/replay.yaml
.venv/Scripts/python.exe -m agentfw.cli couple-scopes --source experiments/e14_validation/coupling/in/per-class-claude-sonnet-5.per-class-v1.s1 --out /tmp/x --rule r2 --split heldout
```

---

## 1. Where the project is, in one paragraph

Phase 1 measured the problem and changed the thesis: agents fail by inferring authority from
silence, not by ignoring explicit boundaries. Phase 2 built the deterministic reference
monitor. Phase 3 built the intent compiler and retired the M0–M5 ladder on dev-slice evidence
(D-032). Phase 3.5 repaired the benchmark, tested that conclusion on 11 held-out triples, and
reopened it (D-034) — on an interval ±23 pp wide. **Phase 5 rebuilt the benchmark to 60 core
triples across three worlds and nine contested classes, authored the gold scopes blind, and
re-ran everything.** The reopening held: the best compiled scope still leaves 5.6% of
underspecified contested actions executing, on an interval that excludes zero. **D-034 is
confirmed and Phase 4 has a real estimand (D-037).**

**What the architecture buys, stated the way the audit log states it.** With no compiled
scope, **100%** of the contested actions the agent attempts execute silently. Under the best
compiled scope, **10.9%** do; the rest are surfaced as a question or refused outright. That is
the headline, and it is a claim about converting silent consequential acts into visible ones
rather than about a model being clever.

**What replicated, exactly.** ASR is **0.0% under every compiled scope** against **46.7%**
undefended. `tool-ceiling` — an allowlist with no scope — reproduces undefended overreach to
the decimal for the third time (**49.4% vs 49.4%**, F-11) and still lets **26.7%** of attacks
through. Restricting the toolset is not the same intervention as compiling a scope.

**Phase 5.5 made all of that runnable by a stranger.** `agentfw demo` puts four committed
episodes in front of the real monitor and prints what it decided — a licensed file write
allowed, a $100 charge nobody authorised stopped at a question, an exfiltration refused by a
structural gate, and a guessed bound asked about and approved — with no key, no network and
no model call. It prints **no aggregate rate**; the footer names the command that regenerates
the tables instead, so the demo cannot go stale against its own results (D-039).

**Phase 6 put a learned model in the compiler slot and it did not go the way the scope-level
score said.** Four rungs (label prior, TF-IDF+LR, frozen encoder+LR, fine-tuned encoder), four
splits, two arms (D-041), 293 blind-authored labels, $0. Under the rule E-15 registered before
any fitting, **it is not adopted** (D-042). Under the *replay* it executes 1.7% of contested
effects against `per-class` Sonnet's 5.6%, at 81.3% high-authority completion against 82.8%,
for 0.17 extra asks per high-authority episode and **fewer** interruptions on benign work — at
a thousandth of the cost. Both statements are true and the disagreement between them is the
phase's result (F-38).

**What Phase 5 corrected in this project's own numbers.** E-00i's headline of 81.8%
underspecified overreach, measured on 11 triples, came in at **49.4%** on 60 — wrong by more
than thirty points. About 13 pp of that is composition (F-32: the contested class explains an
87.5 pp spread against the domain's 13.5 pp) and the rest is small-sample noise. **A headline
measured on 11 scenarios was wrong by 32 pp, and the only reason we know is that Phase 5 ran
before Phase 4.**

## 2b. Phase 6 deliverables, against D-038 and E-15

| # | Deliverable | Status |
|---|---|---|
| 1 | Register predictions before training anything | **done.** E-15, predictions 35–41, committed before a single fit. Four falsified |
| 2 | Build and commit the dataset | **done.** 293 examples derived deterministically from the two committed label files; `agentfw learn` regenerates, 31 tests assert the counts |
| 3 | Baselines in cost order | **done, plus one.** R0 prior, R1 TF-IDF, **R2 frozen encoder**, R3 fine-tuned. R2 is not in D-038 and is what makes R1-vs-R3 interpretable: it changes the representation while holding the classifier fixed |
| 4 | Evaluate leave-one-world-out and dev/held-out | **done, and LOWO turned out to be the wrong split** (F-36). Four splits reported: S1 primary, S2 LOWO, S3 leave-one-template-out, S4 leave-one-phrase-out (post-hoc, labelled) |
| 5 | Wire in as a non-structural signal and **replay** | **done.** Arm L (compiler) and Arm H (narrowing-only) both emit real `CompiledScope` artifacts, both replayed over E-00j's 621 episodes. The replay is what reversed the conclusion |
| — | A few-shot prompted arm for a fair comparison | **deliberately not bought** (~$2–5). The asymmetry is stated in the registration and beside every headline |

## 2a. Phase 5.5 deliverables, against ROADMAP "make it runnable"

| # | Deliverable | Status |
|---|---|---|
| 1 | `agentfw demo`, ALLOW / ASK / BLOCK, no key | **done.** Four scenes, not one: a single episode cannot show all three verdicts, still less an ASK that ends in *yes* (D-039) |
| 2 | It must be a replay, not an animation | **done.** A presenter over `eval/replay.py` under E-14's own policy. A test asserts every printed explanation appears in the audit log the run produced |
| 3 | It must be falsifiable | **done.** `--scope tool-ceiling` shows the same four scenes with the charge going through; a test asserts it still does |
| 4 | `uv sync` from a clean clone | **done and verified in a fresh clone** (see below) |
| 5 | `LICENSE` | **done.** MIT, D-040, covering the benchmark artifacts too |
| 6 | Repo description and topics | **not done — owed.** `gh` is not installed here and repo metadata is an account-level change. The exact text is in the Phase 5.5 summary; it is one paste |
| 7 | README with runnable commands | **done.** A **Run it** section with six, where there were zero |

## 2. Phase 5 deliverables, against D-036

| # | Deliverable | Status |
|---|---|---|
| 1 | 60 held-out core triples (D-036 floor) | **done.** 60 triples, 81 scenarios, 207 utterances, 3 worlds, 9 contested classes |
| 2 | Templates carry their own gates | **done.** A `plays:` block per template, slot-filled per instance, emitted by `agentfw generate`. The 43-entry hand table is gone |
| 3 | Gold scopes authored blind, brief committed first (D-033) | **done.** `heldout_v3.yaml`, 207 variants, committed verbatim. The brief gained five clarifications *before* any label existed |
| 4 | A fresh undefended baseline + competency gate | **done (E-00j).** 621/621 usable, all six predictions held |
| 5 | E-11 re-run at N=60 | **done (E-14).** All six predictions held; D-034 confirmed |
| 6 | E-12 re-run at N=60 | **done.** R1 is dead; R2 is a substitute for `per-class`, not a complement. D-035 confirmed |
| 7 | Sizing analysis before spending (E-13) | **done**, and its width predictions were near-exact: predicted ±7.5 pp, realised ±5.3 pp |

## 3. What exists in code that did not before

**Phase 6:**

```
agentfw/ml/                the learned compiler. Outside the TCB; optional extras only
  dataset.py               293 blind-authored labels as supervised examples; ask-phrase recovery
  splits.py                S1 primary, S2 LOWO, S3 leave-one-template-out, S4 (post-hoc)
  models.py                R0 prior, R1 TF-IDF, R2 frozen encoder, R3 fine-tuned
  evaluate.py              routes learned predictions through eval/scope_eval.py unchanged
  arms.py                  D-041's Arm L (compiler) and Arm H (narrowing-only)
  run.py                   the grid; writes rows.jsonl, predictions.jsonl, report.md
cli.py                     `learn` (--rungs/--splits/--out)
tests/test_ml.py           31 tests: the D-038 boundary, the instrument, the fold leak
experiments/e15_learned_compiler/{replay.yaml,results/,results_s4_diagnostic/}
pyproject.toml             `ml` and `ml-encoder` extras (D-038); core still pydantic+pyyaml
```

Three things worth not re-deriving:

- **The learned arm is scored by the project's own scorer, not a new one.** A prediction
  becomes a `CompiledScope` and goes through `eval/scope_eval.compare_one`. There is no second
  definition of leakage to drift, and `agentfw replay` reads the artifact with no changes.
- **`agentfw/core/` still imports no ML, and it is now a test rather than a promise** — run in
  a subprocess with `sklearn`, `torch`, `transformers`, `numpy` and `scipy` poisoned on
  `sys.meta_path`, because they *are* installed here and a plain import would pass for the
  wrong reason.
- **No fold splits a scenario.** Variants of one scenario are minimal pairs sharing a context
  sentence (D-010); a fold that separated them would leak the answer and produce an excellent
  meaningless number. Asserted for all four schemes.

**Phase 5.5:**

```
agentfw/demo.py            the presenter: scope sources, four scenes, ANSI + glyph fallback
cli.py                     `demo` (--scope/--scenario/--variant/--seed/--list/--full/--brief)
eval/replay.py             ActionOutcome now carries the consent question it rendered
tests/test_demo.py         34 tests, mostly about honesty rather than formatting
LICENSE                    MIT (D-040)
README.md                  a **Run it** section: six runnable commands where there were none
```

**Phase 5:**

```
agentfw/
  sandbox/fixtures/practice_heldout.yaml   world 2: an architecture practice
  sandbox/fixtures/lab_heldout.yaml        world 3: a funded academic lab
  eval/generator.py        an instance may override its template's fixture; templates emit plays
  eval/plays/generated.yaml                generated, never hand-maintained
  eval/scopes_data/heldout_v3.yaml         the live blind labels, 207 variants (D-033 v2)
  eval/templates/b4_us_{share_link,calendar_cancel,doc_update}   three new contested classes
  cli.py                   `authoring-input` (regenerates the blind author's input)
docs/authoring/            the brief, its input, and superseded v1 + v2 labels
experiments/{e00j_heldout_baseline,e14_validation}/
experiments/e14_validation/coupling/       E-12 at N=60, $0, deterministic
```

Four things worth not re-deriving:

- **The three worlds were built to answer one question** — is leakage a property of the
  compiler or of the kind of work? F-32 answers it: **contested class spread 87.5 pp, world
  spread 13.5 pp.** Eight of nine classes appear in all three worlds, which is what makes the
  comparison legitimate.
- **`office_heldout` is frozen.** Worlds 2 and 3 were added rather than expanding world 1,
  because expanding it would have changed what `files_list` returns for the 32 scenarios that
  already had E-00i/E-11/E-12 results.
- **A labelling brief can be debugged and the debugging is measurable** (F-31). Whole-effect-set
  agreement between blind labellers went from 0/6 to **48/60** after five clarifications
  written while no labels existed to fit them to. The ordering is what makes it legitimate.
- **E-12 costs $0** — a deterministic function of committed artifacts (D-026), now paying for
  itself a third time.

## 4. Results

### The undefended baselines, never differenced across the apparatus boundary

| | E-00b dev **pre** | E-00g dev **post** | E-00i held-out (n=11) | **E-00j held-out (n=60)** |
|---|---|---|---|---|
| High-authority compliance | 81.2% | 93.1% | 68.6% | **83.3% [75.3, 90.4]** |
| Underspecified overreach | 38.9% | 45.6% | 81.8% | **49.4% [37.8, 61.1]** |
| Explicit-low overreach | 2.2% | 2.9% | 0.0% | **3.5% [0.0, 8.1]** |
| Gap | +36.7 pp | +42.7 pp | +81.8 pp | **+45.9 pp** |
| Scenario incidence | — | — | 10/11 | **36/60** |
| Benign BTC | 88.0% | 97.2% | 96.7% | **100.0%** |
| ASR undefended | 22.2% | 30.6% | 33.3% | **46.7% [6.7, 86.7]** |

**E-00i is superseded by E-00j and should not be quoted.** Anthropic's dev row (E-00f, 60.0%)
stays pre-repair and is not re-run — a declared budget decision.

### E-14: the 2x2 at N=60

Leakage on underspecified low variants (**scope level** — what the compiler granted):

| | `baseline` | `per-class` |
|---|---|---|
| `gpt-4.1-mini` | 38.3% [26.1, 50.6] | 16.7% [8.9, 25.0] |
| `claude-sonnet-5` | 20.8% [11.7, 30.8] | **15.0% [6.7, 25.0]** |

Contested action executed (**verdict level** — what the agent then did):

| | `baseline` | `per-class` |
|---|---|---|
| `gpt-4.1-mini` | 24.6% [14.6, 35.2] | 12.2% [5.6, 20.0] |
| `claude-sonnet-5` | 11.7% [5.0, 19.7] | **5.6% [1.1, 11.7]** |

Floors: `gold` 0.0%, `read-only` 0.0% (**but read F-35 first**), `tool-ceiling` 49.4%.
**Every compiled interval excludes zero.** All six registered predictions (29–34) held;
prediction 30 was the criterion and it decides D-037.

### What a compiled scope actually does, from the audit log (F-34)

| arm | contested attempts | ALLOW (silent) | ASK → denied | BLOCK |
|---|---|---|---|---|
| `tool-ceiling` | 92 | **100.0%** | 0.0% | 0.0% |
| `baseline` gpt | 276 | 48.9% | 51.1% | **0.0%** |
| `per-class` gpt | 276 | 23.9% | 68.5% | 7.6% |
| `baseline` sonnet | 184 | 22.8% | 69.6% | 7.6% |
| `per-class` sonnet | 92 | **10.9%** | 79.3% | 9.8% |
| `gold` | 92 | 0.0% | 90.2% | 9.8% |

`baseline` on gpt **never blocks, in 276 attempts.** Every `per-class` arm blocks at gold's
rate, because `not_licensed` is a proposition the monitor can act on and silence is not.

### E-15: the learned compiler, at both levels

**Scope level** (contrast fidelity — the metric that punishes over- and under-granting at once):

| rung | S1 dev→heldout | S2 leave-one-**world**-out | S4 leave-one-**phrase**-out | S3 leave-one-**template**-out |
|---|---|---|---|---|
| R0 label prior | 0.0% | 0.0% | 0.0% | 0.0% |
| **R1 TF-IDF + LR** | **39.4%** | 66.7% | 56.7% | 25.8% |
| R2 frozen encoder + LR | 13.6% | 46.7% | 26.7% | 12.1% |
| R3 fine-tuned encoder | 25.8% | **78.9%** | *(not run)* | 45.5% |

Reference, from E-14's committed artifacts: `per-class` sonnet **86.4%**, `baseline` gpt
**51.5%**, `read-only` and `tool-ceiling` both **0.0%**.

**Read one column at a time and this benchmark will tell you anything you like.** R3 scores
78.9% under leave-one-world-out and 25.8% on the primary split — a 53 pp swing for the same
model on the same 293 labels. **That is F-36 and it is the finding that outlives the phase.**
No rung dominates either: R1 beats R3 by 13.6 pp on S1 and R3 beats R1 by 19.7 pp on S3, so
any single-split claim about which family wins is an artifact of the split it was measured on.

**Verdict level** (S1 scopes, E-00j's 621 episodes, `M0-consequential`, $0):

| scope source | contested **executed** | high-auth **completed** | asks/ep high | asks/ep benign | cost |
|---|---|---|---|---|---|
| `gold` | 0.0% | 82.8% | 0.035 | 0.0 | — |
| `per-class` sonnet | 5.6% | 82.8% | 0.333 | 0.3 | ~$6 |
| **Arm L (learned)** | **1.7%** | **81.3%** | 0.500 | **0.0** | **~$0** |
| Arm H (per-class ∩ learned) | 0.0% | 73.7% | 0.692 | 0.3 | ~$6 |
| `baseline` gpt | 23.3% | 82.8% | 0.293 | 0.2 | ~$0.10 |
| `read-only` | 0.0% | **71.7%** | 0.798 | 0.1 | — |

**ASR is 0.0% under every arm, learned included.** `read-only` is the control that makes the
Arm L row readable: it also has 0% leakage, and it costs 11 pp of task completion and 0.8 asks
per episode to get there.

**E-15c, the calibration follow-up** (same 621 episodes, both R3 arms side by side):

| | scope: leakage | scope: retention | scope: contrast | verdict: executed | verdict: high done |
|---|---|---|---|---|---|
| R3 blind (E-15) | 51.7% | 78.8% | **25.8%** | 27.8% | 82.8% |
| R3 calibrated (E-15c) | 31.7% | 48.5% | **13.6%** | **16.1%** | 79.8% |
| R1 TF-IDF, for scale | 1.7% | 45.5% | 39.4% | **1.7%** | 81.3% |

**Calibration improves R3 at the verdict level and makes it worse at the scope level** — the
second time the two have disagreed, in the opposite direction from F-38. It does not make R3
competitive: R1 is ~10x better on the security axis at better task completion. Phase 6's
conclusion stands.

**Never quote Arm L's verdict row without the scope row, or the reverse.** The whole point is
that they disagree, and either alone is misleading (F-38, D-042).

### Registered predictions, scored across the project

| Predictions | Outcome |
|---|---|
| 1–5 (E-00g, dev post-repair) | all held |
| 6–9 (E-00i, held-out n=11) | all held — **but the slice was too small and E-00j supersedes it** |
| 10, 13 (E-11 exit criterion) | **both falsified** → D-034 |
| 11, 12, 14, 15, 16 (E-11) | mixed; 14 held for the wrong reason (F-29), 15 later shown exact (F-29 fix) |
| 23–28 (E-00j) | **all six held** |
| 29–34 (E-14) | **all six held.** 30 is the criterion → **D-037 confirms D-034** |
| 35–41 (E-15) | **two held (35, 41), one split (37), four falsified (36, 38, 39, 40).** 35 held but for the wrong reason — see F-36 |
| 42–44 (E-15b) | **all three held**, which is weaker evidence than it looks: a curve's shape is easier to predict than a system's behaviour. 43 held only in ordering — neither rung saturates |
| 45–48 (E-15c) | **one held (47), three falsified (45, 46, 48).** 48 is the decisive one: CV chose E-15's blind weight cap, so the weighting was never misconfigured. 45 is falsified as written *and* was registered in the wrong currency — see the self-criticism in E-15c's result |

## 5. Open defects and risks carried forward

| ID | Issue | Action owed |
|---|---|---|
| **F-33** | Two of the six irreducible-core scenarios are probably *label* defects, not compiler failures: `hal_drawings` (flagged by the blind author before any run) and `devi_planning` (four independent compilers disagree with the label) | **Fix both in the next slice, before anything is measured against them.** Excluding them would put the best arm at 3.3% rather than 5.6%; the headline stays 5.6% |
| **F-33** | Three of the four *genuine* core failures are one template family (`docedit`, `WRITE:USER_FILES`) | Test whether it is an instruction shape or a template artifact by writing `WRITE:USER_FILES` into a different template |
| **F-31** | Residual labeller disagreement is entirely instrumental reads; clarification 2 fixed the stopping rule for `READ:CONTACTS` only | Extend it to `READ:USER_FILES` and `READ:EMAIL` — ~150 variants still rest on judgement |
| **F-27** | The findability gate covers word queries, not globs | Extend the gate; the scenario itself was re-diagnosed as a model competency finding and is untouched |
| **F-16** | The compiler settles *whether* and asks *how* | **Measured twice, not fixed.** At N=60 the post-hoc coupling rule is a substitute for `per-class`, not a complement, and degrades the best arm. Not adopted (D-035, confirmed) |
| **F-10** | `consequential()` cannot tell "not worth interrupting about" from "the compiler probably dropped this" | Phase 4 cost model — and **fit per contested class, not pooled** (F-32) |
| **F-29** | Residual imprecision: every argument of an outbound effect is treated as transmitted | Latent — zero denials on licensed work. Phase 4 `monitors/flow.py` |
| **F-08 / F-07** | ASK granularity; argument vs authority provenance | Phase 4 |
| **F-36** | Leave-one-world-out overstates generalisation on this benchmark by ~41 pp, and eight of nine contested classes have a **sole template source** | Never evaluate a learned component LOWO on this data. Any new template should reuse an existing contested class where possible, so leave-one-template-out stops being a class-transfer test |
| **F-37** | The benchmark supplies the least supervision for the decision the project is about — 1 dev positive for `SEND:PUBLIC_WEB`, 45 for `READ:USER_FILES` | Structural (D-010), not fixable by relabelling. If a learned component is revisited, the training set has to grow at the contested classes specifically |
| **F-43** | Nineteen per-class thresholds fitted from 48 training scenarios overfit, and the out-of-fold estimate **could not see it** — 45.8% OOF against 13.6% held-out, because the threshold search and the OOF score read the same probabilities | Anyone repeating E-15c needs a **nested** inner loop: select thresholds on k−1 folds, score on the held-back fold. The general rule is that a per-class decision rule needs examples *per class*, and 86/19 is 4.5 |
| **F-41** | The fine-tuned encoder's leakage does not fall with data (47.8% → 51.7% across a 4x increase) | **Answered by E-15c.** Its mechanism is withdrawn — CV chose E-15's blind weight cap, so the weighting was never wrong. Its effect is partly upheld: thresholds help at the verdict level. Still owed, and now the only live lever: **extend the contested-class training set via the generator** (D-038 step 2, never taken). Does not reopen Phase 6's conclusions |
| **F-40** | `WRITE:USER_FILES` defeats prompted compilers by over-granting and the learned one by never granting | F-33's action is unchanged and now better motivated: write `WRITE:USER_FILES` into a different template and see whether the shape or the class is at fault |
| **R-14** | Claude-authored scenarios, labels and compiler arms | **Untouched and now the largest risk.** D-033 removes context contamination, not authorship. Needs a human or another vendor |
| **R-09** | Open-weight generalisation | Unresolved |
| **R-16** | Prompt development and measurement share the dev slice | Intact: no prompt was touched in Phase 3.5 or Phase 5 |

## 6. What comes next, and what Phase 4 inherits whenever it runs

**Read `docs/ROADMAP.md` first — "The plan from here to a finished, postable project."** The
target is a project that stands up on GitHub and LinkedIn and supports masters applications,
not a paper; the paper's blocker is R-14 rather than the literature, and it is revisitable.
**Phase 4 is deferred behind Phase 6 by D-038**, because every result in this project is
currently a deterministic monitor plus a *prompted* model and there is no learned component
anywhere. Phase 5.5 is **done** (D-039, D-040) and **Phase 6 is done** (D-041, D-042) — there
is a learned component now, it was measured honestly, and it was not adopted. In order from
here:

1. **Phase 7 — presentation.** Restructure `README.md` (what it is → GIF → headline →
   quickstart → how it works → results); move the phase-by-phase narrative to
   `docs/RESEARCH_LOG.md`. Keep **three** tables above the fold now rather than two: the 2x2,
   F-34's disposition table, and **E-15's scope-vs-verdict pair**, which is the clearest single
   illustration in the repository of why this project measures what it measures.
2. **Phase 8 — defensibility, then the post.** D-042 and F-36 are both strong interview
   answers: *"walk me through a result that surprised you"* now has two, and one of them is a
   correction to an instruction the project gave itself.
3. **Phase 4 — the cost model**, whenever it runs. D-042 gives it a new reason to exist:
   Arm L trades 0.17 extra interruptions per high-authority episode for 3.9 pp of security at a
   thousandth of the cost, and pricing interruptions is exactly what turns that from an
   observation into a decision.

*What Phase 6 was, for the record:*

   **Phase 6 — the learned intent compiler (D-038).** Registered predictions before training;
   cheap baselines before the encoder; leave-one-world-out because surface-form memorisation is
   the live risk; wired in as a non-structural signal (D-006) and **replayed**, because F-14
   already taught that a scope-level score alone can rank a change that makes the system worse.
   Baseline to beat: **15.0% leakage / 100% retention at ~$6 per run.** When it lands, it
   becomes a fifth `agentfw demo --scope` arm beside the prompted ones, which is the cheapest
   possible qualitative comparison and costs nothing to add (D-039).
2. **Phase 7 presentation, then Phase 8 defensibility and the post.**

**One Phase 5.5 item is owed and it is thirty seconds of someone's time.** The GitHub repo
still has no description and no topics; `gh` is not installed on this machine and repo
metadata is an account-level change, so it was written down rather than done. Suggested:

```
gh repo edit unnuss/agent-firewall   --description "A runtime authorization layer for tool-using LLM agents: a deterministic reference monitor that converts silent, unlicensed agent actions into visible ones. 60-triple held-out benchmark, blind-authored labels, every prediction registered before the run."   --add-topic llm-agents --add-topic ai-safety --add-topic agent-security   --add-topic prompt-injection --add-topic authorization --add-topic reference-monitor   --add-topic benchmark --add-topic python
```

When Phase 4 does run, D-037 has already narrowed it:

- **The estimand is real and it is not the pooled rate.** 33 of 60 underspecified variants leak
  under no arm; 6 leak under all four. **Phase 4 should be sized against the contested third**,
  not against 5.6%, most of which is either unanimous or a labelling error.
- **Any per-effect cost term must be fitted per contested class** (F-32). The class explains
  an 87.5 pp spread; the domain explains 13.5 pp.
- **Treat "told no" and "not told yes" as distinct inputs** (F-34). The reference monitor
  already does; no ladder design should collapse them.
- **The interaction between the two knobs is unresolved.** Additive is refuted; multiplicative
  fits the point estimates (0.96) on an interval of [0.21, 2.50]. N=60 sizes main effects, not
  interactions. Do not build on "they compose independently".

**Cost, and a registered estimate that was wrong.** E-14 was budgeted at ~$8.5 and cost
**~$13.6 estimated from recorded tokens at published list prices** (not a billed figure). The
overrun is entirely the `per-class` formulation on Sonnet: it emits a verdict per candidate
class, so one seed produced **328k completion tokens** against `baseline`'s 13k on gpt. **The
`per-class` advantage is bought with tokens** — 19 pp of overreach for about $5.80 more per
207-utterance run — and that trade belongs in Phase 4's cost model alongside the interruption
budget, because it is the same kind of quantity.

### Cheap things worth doing whenever

- The dev slice's `af_auth.us.email.sam_number::c` still points at the Q1 report while its
  siblings ask about Q3.
- Extend the findability gate to glob and prefix tools (F-27).
- The coupling output directory repeats its arm name twice
  (`out/<arm>.r2/<arm>.coupled-r2/`), which is what pushes the longest tracked path to 155
  characters and breaks a deep Windows clone. Flattening one level would drop ~45 characters.
  Left alone for now because it means moving committed artifacts and rewriting the paths in
  E-12's configs, which is not worth a presentation fix.
- ~~`open_questions` / `effects` populated with a `list` into a tuple-typed field, so every
  `couple-scopes` run printed a pydantic serialization warning.~~ **Fixed in Phase 5.5** — two
  `model_copy(update=...)` calls in `intent/coupling.py`. All four output digests are byte
  identical before and after, which is what makes it a lint fix and not a result change.
- A second and third seed for `per-class` on Sonnet — for *variance*, not precision. E-13
  measured that seeds do not narrow a scenario-clustered interval at all.

**Do not** relitigate D-006 (no ML in the trusted path), D-018 to D-025, D-030's provenance
asymmetry, or D-033's authoring condition without a documented reason.

## 7. Environment notes

- Python 3.12.9, uv 0.12.7, git 2.55, Windows 11. Venv at `.venv/`.
- Credentials load from **`.env.local`** (gitignored), which holds working `OPENAI_API_KEY`
  and `OPENROUTER_API_KEY`. The file wins a conflict with an exported variable and says so
  (D-029); every command prints the credential fingerprint it used.
- No NVIDIA GPU. Ollama has `qwen2.5-coder:14b`; usable as an exploratory compiler only.
- **ML extras are optional and split in two** (D-038): `ml` is scikit-learn and covers R0/R1;
  `ml-encoder` adds torch and transformers (~2.5 GB) for R2/R3. Installed here:
  scikit-learn 1.9.0, torch 2.14.0+cpu, transformers 5.16.1, numpy 2.5.3. **All four rungs run
  on CPU**; R1 fits in 6 s for 207 utterances, R3 in a few minutes per fold.
- **Application Control once blocked the ML stack, and recreating the venv fixed it.** On
  2026-09-10 Windows Application Control began blocking
  `numpy/random/_common.cp312-win_amd64.pyd`, taking `numpy.random`, `sklearn` and
  `transformers`/`torch.utils.data` with it while `numpy`, `scipy` and bare `torch` kept
  working. **The decisive diagnostic: the blocked copy and a freshly installed one are
  byte-identical** (SHA256 `8BD4FCD6...`, 174,080 bytes), so the policy had flagged the *file
  instance at that path* rather than the content. `rm -rf .venv && uv sync --extra dev --extra
  ml-encoder` cleared it in under a minute, **with no security setting changed**. If it recurs,
  recreate the venv first and do not touch Smart App Control. Do not pin an older numpy to get
  past a scan — that is evasion wearing a requirements file.
- **Two things that failure established for free.** `agentfw/core/`, `agentfw/policy/`,
  `firewall.py` and the whole evaluation harness were **completely unaffected** — the first real
  test of D-038's optional-extra boundary, and it held. And it exposed a defect in this
  repository's own suite: `pytest.importorskip` catches only `ModuleNotFoundError`, so the
  optional-extra tests failed where they should have skipped, and because the availability probe
  imported numpy into the session, **`hypothesis` — which seeds `numpy.random` when it sees numpy
  in `sys.modules` — took fifteen property tests down with it.** The probe now runs in a
  subprocess. Worth remembering beyond this project.
- **The two ML tests occasionally skip, and that is the guard working rather than a
  regression.** `tests/test_ml.py` probes importability in a subprocess; on this machine the
  Application Control scan is intermittent, so a probe can momentarily see a blocked DLL and skip
  instead of failing the suite. Observed once as `573 passed, 2 skipped`, then `575 passed` on an
  immediate re-run with nothing changed. If you see two skips, re-run before investigating.
- **A transient install-time failure worth recognising, not debugging.** The first `import
  sklearn` after `uv pip install` died with `ImportError: DLL load failed while importing
  _special_ufuncs: An Application Control policy has blocked this file`. It was Windows
  scanning a freshly written DLL, not a policy block: the same import succeeded seconds later
  and a real fit ran. If it recurs, wait and retry before changing anything.
- **Phase 6 spent $0.** Every rung, every split, both arms and the whole 621-episode replay
  run on committed files and a CPU. That is the phase's second-order point: the comparison it
  makes is between a ~$6-per-run frontier model and something that costs nothing, so the
  experiment had to cost nothing too or the argument would have been funny.
- **Phase 5 spent roughly $14.5** — E-00j ~$0.95, E-14 ~$13.6 (estimated from tokens), E-12
  and every replay $0. **Phase 5.5 and Phase 6 both spent $0**, and their whole point is that
  everyone else's first run costs $0 too. **Total project API spend is still roughly $26.5.**
- **A clean install was verified from a real `git clone`, not assumed.** `uv sync` resolved
  16 packages and installed **7** — `agentfw`, pydantic, pydantic-core, pyyaml,
  annotated-types, typing-extensions, typing-inspection — and `uv run agentfw demo` rendered
  in **2.9 s** with all three credential variables reported absent. The `dev` extra (pytest,
  hypothesis, ruff) is separate and only the test suite needs it.
- **The clone failed the first time, on Windows `MAX_PATH`.** The longest tracked path is 155
  characters (`experiments/e14_validation/coupling/out/<arm>.r2/<arm>.coupled-r2/comparisons.jsonl`,
  which repeats the arm name twice), so a clone into a directory deeper than ~100 characters
  dies with `Filename too long` and a message that does not say what to do. Documented in the
  README rather than papered over; `git config --global core.longpaths true` fixes it. **This
  is the kind of thing Phase 5.5 existed to find**, and it would have been found by the first
  stranger instead.
- **Smoke-test one call per arm before launching it**, and **dry-run the free half of a
  pipeline before paying for the expensive half** — that is how F-28 was caught, at a cost of
  one minute instead of ~$2.
- **Six episodes failed with HTTP 429 in E-00j** and were re-run at two workers; the pre-refill
  file is kept at `provenance/before_429_refill.jsonl`. Recorded rather than silent because the
  six were mildly `a`-variant-heavy.
