# PROJECT STATE

**Read this first.** It is the handoff document between development sessions.

**Last updated:** 2026-09-06 · **Phase 5 complete.** The validation ran at N=60: the benchmark
was rebuilt to three worlds and 60 core triples, gold scopes were authored blind, and E-11 and
E-12 were re-run on them. **D-034 is confirmed on adequate power (D-037).** · **Next: Phase 4,
the cost model, sized against the contested third rather than the pooled rate. See section 6.**

---

## 0. If you are the next session, do exactly this

1. Read `CLAUDE.md`, then this file, then **`docs/DECISIONS.md` D-037** — it is the verdict on
   the whole Phase 3.5/Phase 5 arc and it says what Phase 4 inherits. Then **D-034** (what was
   reopened), **D-036** (why Phase 5 ran before Phase 4), **D-035** (the coupling rule, still
   not adopted), **D-033** (how the held-out labels were authored), and **D-032** (reopened;
   read it for the argument, D-037 for its status).
2. Read findings **F-32 → F-33 → F-34** in `docs/EXPERIMENTS.md`, in that order. F-32 says the
   contested effect class explains six times more variance than the domain; F-33 says the
   residual is six utterances and not a rate; F-34 says the two prompt formulations differ in
   what they can *express*, not only in how well they guess. Reading any one alone overstates
   it.
3. **Then** read **F-16 → F-17 → F-18 → F-19** for Phase 3's argument on the dev slice — but
   read them knowing F-19's "substitutes" reading did not survive N=60, and the interaction is
   still unresolved (E-14, last paragraph).
4. Read **F-29** before quoting any compliance number, and **F-35** before quoting `read-only`
   as a floor.
5. **The apparatus boundary is real.** Every number from E-00, E-00b, E-00f, E-00h, E-01a and
   E-01b is **pre-repair**; everything from E-00g onward is **post-repair**. A `CONTRACT.md`
   sits in each pre-repair result directory. Never difference across it.

Health check (~12 min, no API calls, no keys needed):

```bash
.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m agentfw.cli validate
```

Expect **481 passed, 0 failed**. The four gold-scope tests that were red on purpose through
Phase 5's authoring step are green: the labels exist now. Any failure is a real one. `validate`
reports 24 AF-Auth / 6 AF-Inject / 18 benign **dev** scenarios and **66 AF-Auth / 5 AF-Inject /
10 benign held-out**, 23 tools.

Four experiments reproduce with no key and no money:

```bash
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

**What Phase 5 corrected in this project's own numbers.** E-00i's headline of 81.8%
underspecified overreach, measured on 11 triples, came in at **49.4%** on 60 — wrong by more
than thirty points. About 13 pp of that is composition (F-32: the contested class explains an
87.5 pp spread against the domain's 13.5 pp) and the rest is small-sample noise. **A headline
measured on 11 scenarios was wrong by 32 pp, and the only reason we know is that Phase 5 ran
before Phase 4.**

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

### Registered predictions, scored across the project

| Predictions | Outcome |
|---|---|
| 1–5 (E-00g, dev post-repair) | all held |
| 6–9 (E-00i, held-out n=11) | all held — **but the slice was too small and E-00j supersedes it** |
| 10, 13 (E-11 exit criterion) | **both falsified** → D-034 |
| 11, 12, 14, 15, 16 (E-11) | mixed; 14 held for the wrong reason (F-29), 15 later shown exact (F-29 fix) |
| 23–28 (E-00j) | **all six held** |
| 29–34 (E-14) | **all six held.** 30 is the criterion → **D-037 confirms D-034** |

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
| **R-14** | Claude-authored scenarios, labels and compiler arms | **Untouched and now the largest risk.** D-033 removes context contamination, not authorship. Needs a human or another vendor |
| **R-09** | Open-weight generalisation | Unresolved |
| **R-16** | Prompt development and measurement share the dev slice | Intact: no prompt was touched in Phase 3.5 or Phase 5 |

## 6. What Phase 4 inherits

D-037 discharges Phase 3.5's obligations and narrows Phase 4's work:

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
- `open_questions` is declared `tuple[str, ...]` but populated with a `list`, so every
  `couple-scopes` run prints a pydantic serialization warning. Harmless (both serialize to a
  JSON array) but noisy; fix the annotation or the constructor.
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
- **Phase 5 spent roughly $14.5** — E-00j ~$0.95, E-14 ~$13.6 (estimated from tokens), E-12
  and every replay $0. **Total project API spend is roughly $26.5.**
- **Smoke-test one call per arm before launching it**, and **dry-run the free half of a
  pipeline before paying for the expensive half** — that is how F-28 was caught, at a cost of
  one minute instead of ~$2.
- **Six episodes failed with HTTP 429 in E-00j** and were re-run at two workers; the pre-refill
  file is kept at `provenance/before_429_refill.jsonl`. Recorded rather than silent because the
  six were mildly `a`-variant-heavy.
