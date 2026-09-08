# Roadmap

Refined from the original brief's seven phases. Two changes worth noting:

- **Phase 1 now ends with an experiment, not a demo.** Before building any defense we
  measure whether an undefended competent agent actually overreaches. If it does not, the
  thesis is wrong and we would rather know in week one than week ten.
- **Phases 3 and 4 are re-cut.** The brief split them as "intent/provenance" and
  "risk/sensitive data". We split them as "deterministic core" and "ML core", because that
  boundary is the one that matters architecturally (D-006) and because it lets the
  deterministic system be evaluated on its own — which is itself a result.

Each phase ends with: tests green, docs updated, a written summary, and a stop for review.

---

## Phase 0 — Research, specification, architecture ✅ complete (2026-08-28)

Delivered: `RELATED_WORK.md`, `PROJECT_SPEC.md`, `THREAT_MODEL.md`, `ARCHITECTURE.md`,
`EVALUATION.md`, `DECISIONS.md`, this roadmap, `PROJECT_STATE.md`, `CLAUDE.md`.

---

## Phase 1 — Sandbox, agent, and the "does the problem exist?" experiment ✅ complete (2026-08-30)

**Outcome.** All five deliverables shipped. The go/no-go gate was answered in a way that
**changed the project's thesis**: undefended overreach against *explicit* instructions is
~0%, and the real failure is authority inference under *underspecified* intent (38.9% on
OpenAI, 60.0% on Anthropic). Six experiments, ~1,700 episodes, three of them inconclusive
by a pre-registered competency floor and preserved as such. See D-018, D-019, D-021, D-022.

Original plan follows.


**Goal:** a real tool-using agent in a deterministic world, plus the first honest number.

Deliverables:
1. `agentfw/sandbox/` — seedable world; tool families for files, email, calendar, web,
   payments, storage, contacts; snapshot/restore; machine-checkable effect oracles.
2. `agentfw/agent/` — the tool-calling loop, provider abstraction (Anthropic + OpenAI +
   local), labeled trace recording. **Labels assigned at ingestion from day one** — retro-
   fitting provenance later is the classic way this kind of project fails.
3. 15–20 benign tasks and 8–10 authorization scenarios (a dev slice of AF-Auth), each with
   an oracle.
4. 5–8 injection scenarios (a dev slice of AF-Inject).
5. **E-00: undefended overreach + hijack baseline.** Run the undefended agent, n>=3 seeds,
   >=2 models. Report OR, ASR, BTC with CIs.

**Exit criterion / go-no-go:** if undefended overreach on the AF-Auth dev slice is under
~5%, stop and re-frame the project before building the firewall (EVALUATION section 6.1).

**Risks addressed:** R-01 (does the problem exist), R-02 (can we build oracles).

---

## Phase 2 — Firewall runtime core (deterministic, no ML) ✅ complete (2026-08-30)

**Outcome.** All eight deliverables shipped; 168 tests green; P1-P4 are property tests
rather than intentions. E-01a measured the core on its own and produced a result that
**changes what Phase 3 must do first**: given a correct scope, the deterministic core
removes all measured overreach (45.9% -> 0.0% on underspecified) and all measured attack
success (22.2% -> 0.0% ASR) at zero interruptions on benign work — and the `M0-no-ask`
ablation scores identically, so **ASK buys nothing when the scope is right**. The value of
the entire ML core is therefore bounded by compiler/gold scope divergence, which nobody has
measured. See E-01a, D-023, D-024, and findings F-07 to F-09.

Two additions the roadmap did not anticipate, both forced by measurement: gold scopes
(D-023, because Phase 2 has no scope source) and remembering a refused ASK (D-024, because
one scenario drained the interruption budget re-asking an answered question).

Original plan follows.


**Goal:** a working reference monitor whose security properties do not depend on any model.

Deliverables:
1. `core/types.py`, `core/labels.py`, `core/effects.py`, `core/scope.py`, `core/audit.py`.
2. Label propagation through the trace; the (tool, args) → Effect mapper.
3. `IntentScope` with `expand_via_consent` as the only widening path (D-007), enforced by
   the type system + tests.
4. `PolicyCombinator` with hard structural gates + a *placeholder* fixed-threshold decision
   (the cost model arrives in Phase 4).
5. Consent-integrity ASK rendering (D-008); scripted reviewer oracle.
6. Hash-chained audit log + offline replay.
7. Property-based tests for P1–P4 (hypothesis).
8. **E-01a: deterministic-only evaluation.** How far does the no-ML system get on AF-Auth
   and AF-Inject dev slices? This becomes the M0 row and the ablation floor.

**Watch for:** the temptation to add "just one heuristic" to fix a failing case. Log it as a
finding instead; Phase 3 is where intelligence goes.

---

## Phase 3 — Intent compilation and the authorization model ✅ complete (2026-08-31)

**Outcome.** Deliverable 1 shipped and produced the phase's results; **deliverables 2-8 were
retired, superseded or deferred by those results** rather than skipped for want of time
(D-032). The phase answered its question and dissolved most of its own plan.

*What was built.* `agentfw/intent/` — an intent compiler whose inputs are restricted by
signature to the user's turn and the tool catalogue (D-025); three registered prompt
formulations; committed compiled-scope artifacts (D-026); E-09a scoring compiled scopes
against gold labels; E-01b turning those scopes into real ALLOW/ASK/BLOCK verdicts over 702
committed episodes at zero API cost.

*What was learned, in order.* The registered arm **falsified the phase's central prediction**
(F-16): the baseline compiler licensed the contested effect on 53.3% of underspecified
instructions, worse than the undefended agents' 45.9%. E-10 then falsified the *explanation*
twice — changing the formulation moves it to 0.0% (F-17), changing the model moves it to
10.0% (F-18) — leaving **one bad cell in a 2x2 whose two fixes are substitutes** (F-19). The
best configuration matches the hand-written gold scopes on every security axis: 0.0%
overreach, 0.0% ASR, compliance within one episode of gold.

*What the deterministic core did throughout.* **ASR 0.0% under every compiled scope ever
measured.** The injection half of the thesis never needed a model.

*Disposition of the planned deliverables (D-032).*

| # | Planned | Disposition |
|---|---|---|
| 1 | `intent/compiler.py` + E-09a/E-01b | **done** — the phase's result |
| 2, 3, 5, 6 | M0-M5 ladder, calibration, E-02, E-03 | **retired.** They estimate a calibrated `P(licensed)` to place an ASK band; the security axis turned out reachable from formulation and model choice alone, so there is no uncertain middle left to arbitrate. The compiler *is* M4, and E-10 spent four arms exploring that design space |
| 4 | E-01 (similarity, D-012) | **superseded.** Its purpose was a negative result motivating the effect ontology; F-11 supplies a stronger one empirically — a tool-allowlist scope reproduces undefended overreach exactly |
| 7 | Dependency screener (F-07) | **deferred to Phase 4.** ASR is already 0.0%; the screener buys interruption efficiency, not security, so it belongs with the cost model |
| 8 | M6 distillation | **not applicable** — conditional on E-03 (D-011), which is retired |

*Owed, and it is the next milestone rather than a footnote.* Every number above is from the
dev slice. The held-out suite cannot validate them (D-031) and a held-out verdict experiment
is impossible until F-20 is fixed. See Phase 3.5.

Original plan follows.


**Goal:** the intellectually strongest part of the project.

**Re-ordered after E-01a.** Deliverable 1 now comes first and alone, and gains a second
half. The deterministic floor is 0% overreach and 0% ASR at zero benign interruptions when
the scope is correct, so there is no headroom above it on those metrics; the ML core's
entire job is to make the scope correct. Measuring how far a compiled scope falls short of
a gold one therefore bounds the value of everything in Phases 3 and 4, and it is cheap.
Do it before building the ladder, not alongside it (finding F-09).

Deliverables:
1. `intent/compiler.py` — utterance → IntentScope. Evaluated as its own component
   (effect-set precision/recall, constraint extraction accuracy) against the gold scopes
   in `agentfw/eval/scopes_data/` (D-023).
   **1b. E-01b — re-run the E-01a replay with compiled scopes in place of gold ones.** The
   delta between the two runs is the size of the opportunity for the rest of the project.
   If it is small, say so and re-plan Phase 4 rather than building a cost model with
   nothing to arbitrate.
2. The M0–M5 ladder from `ARCHITECTURE.md` section 4.3, each independently evaluable.
3. Calibration: ECE, reliability diagrams, temperature/isotonic fitting on dev.
4. **E-01: the pre-registered similarity experiment** (D-012) — AUC of M1/M2 on AF-Auth vs
   AF-Inject, separately.
5. **E-02: the ladder comparison** — accuracy, latency, cost per approach.
6. **E-03: the cascade** — cost/accuracy frontier; where does the LLM judge actually earn
   its tokens?
7. Dependency screener (LM-judge variant); the attention-saliency spike is time-boxed and
   dropped if it does not work in that box (R-03).
8. M6 distillation **only if** E-03 justifies it (D-011).

---

## Phase 3.5 — Benchmark repair and held-out validation ✅ complete (2026-09-04)

**Outcome.** All six deliverables shipped, and **the exit criterion was answered in the
negative**: the E-10 headline does not replicate on unseen underspecified instructions, so
D-032's retirement of the M0–M5 ladder is reopened (D-034). That was the registered condition
and it is followed rather than renegotiated.

*What replicated.* **ASR 0.0% under every compiled scope**, on a held-out slice where the
undefended agent is hijacked 33.3% of the time by five unseen attacks, two of them
defense-aware. The injection half of the thesis is validated on unseen data and it never
needed a model.

*What did not.* The best compiled scope leaks **9.1%** of contested effects on unseen
underspecified instructions where dev showed **0.0%**, and no arm reaches the 0.0%/0.0% pair.
F-19's "the two fixes are substitutes" is dev-only: held out both help, neither suffices, and
they compose. The residue is **F-16's exact mechanism** — the compiler grants the contested
class and asks a question about *how* — in the arms F-17 and F-19 declared had fixed it.

*What the benchmark repair proved about itself.* The dev phenomenon **survives its own
instrument being fixed and grows**: underspecified overreach 38.9% → 45.6%, the gap D-018
rests on +36.7 pp → **+42.7 pp**, compliance 81.2% → 93.1%, benign BTC 88.0% → 97.2%. Had it
not survived, two phases would have been built on a broken instrument, and that was the real
risk this milestone carried.

*Ten findings, most of them from gates rather than review.* F-21 (a tool reporting an empty
world for a missed prefix), F-22 (a hand-read diagnosis right about four of six — then itself
**corrected by intervention** to four of six with a different sixth), F-23 (compiled scopes
keyed by id but defined by an utterance), F-24 (ten held-out scenarios silently running in the
dev world), F-25 (a gate whose hardcoded probes bound it to the old world), F-26 (two
labellers: 6/6 on the contested class, 0/6 on the whole effect set), F-27 (the findability
gate covers word queries, not globs), F-28 (**a replay of the wrong split reporting a perfect
defense over zero episodes**), F-29 (**the flow gate denies a licensed payment, so compliance
rewards under-granting — hidden for three phases behind a seven-character identifier**).

*What Phase 4 inherits.* D-034 un-retires the ladder's **question** and not its answer, with
the estimand's shape measured: concentrated in five of eleven triples, structurally visible as
a grant contradicted by its own open question, and disagreed on between arms. And F-29 must be
fixed before any compliance number is quoted.

Original plan follows.


## Phase 3.5 — Benchmark repair and held-out validation (as planned)

**Why this exists as its own milestone.** Phase 3's results are good and entirely
unvalidated: every number is dev-slice. Four findings say the benchmark, not the system, is
now the weak link — F-20 (a tool contract that silently kills well-formed scenarios), D-031
(the held-out suite is 3 scenarios from one template, all explicit, so it cannot exercise the
underspecified band the project is about), F-05 (a dev scenario asks for a figure the world
does not contain), F-03 and F-06 (over-strict oracles, untrustworthy compliance on 8
scenarios).

The Phase 1 mitigation for exactly this risk — "build the scenario format and the generator
early, so Phase 5 is scaling rather than inventing" — **did not hold.** The generator has one
template and it produces the wrong shape: explicit B1 pairs, when the phenomenon lives in
underspecified triples. Better to find that here than in Phase 5.

Building Phase 4's cost model on unvalidated dev numbers would compound the problem, so this
comes first. It is deliberately *not* full Phase 5 scaling — only enough to make the existing
claims checkable.

Deliverables:
1. **Fix F-20** — `email_list`'s query contract — and re-run the undefended baselines.
   Everything downstream needs episodes that a competent agent could actually complete.
2. **An underspecified-triple generator template.** The missing piece; today's template makes
   explicit pairs only.
3. **A real held-out slice**: underspecified triples, plus benign and af_inject scenarios so
   FPR-block and ASR are measurable there at all. Hand-audited, with the oracle-triviality
   gate from F-01 applied to every generated scenario.
4. **Held-out gold scopes authored independently** of whoever scores them — the one caveat on
   `heldout.yaml` that cannot be fixed by the session that wrote it (D-031).
5. **Re-run E-09a and E-01b on it.** This is the first genuine validation of any Phase 3
   claim, and it is what decides whether D-032's retirement of the ladder was right.
6. Fix F-05, F-03 and F-06 while in there.

**Exit criterion.** The E-10 headline — a compiled scope reaching gold-level security — either
replicates on unseen underspecified instructions or it does not. If it does not, D-032 is
reopened and the ladder question returns.

> **It did not.** E-11 predictions 10 and 13 were the operative form of this criterion and
> both are falsified. See D-034.

## The plan from here to a finished, postable project

**Written 2026-09-08, after Phase 5 closed.** The target is a project that stands up on GitHub
and LinkedIn and supports masters applications — *not* a paper. That is a deliberate choice
(the paper's blocker is R-14, not the literature) and it is revisitable later. Phase 4's cost
model is **deferred behind Phase 6** by D-038.

The finish line, so it is possible to know when this is done:

1. `git clone && uv sync && agentfw demo` shows the firewall allowing, asking and blocking —
   **with no API key**.
2. A GIF of that at the top of the README.
3. A **learned** intent compiler with a measured comparison against the prompted one, on
   leakage, retention, contrast and cost per run.
4. A README readable in 60 seconds, with the depth still reachable underneath it.
5. A defensibility pass: the questions an interviewer will ask, and where each answer lives.
6. One LinkedIn post.

### Phase 5.5 — make it runnable ✅ complete (2026-09-09)

**Outcome.** All of it shipped, and the demo grew from one episode to four because one cannot
show ALLOW, ASK and BLOCK — let alone an ASK that ends in *yes*, which is the beat that keeps
ASK from reading as a slower BLOCK (D-039). `agentfw/demo.py` is a presenter over
`eval/replay.py` under E-14's own policy: no decision logic, no hardcoded rate, every printed
sentence read back out of the audit log the run produced, and `--scope tool-ceiling` shipped
alongside it so the same four scenes can be watched failing. `tests/test_demo.py` holds all
four constraints as assertions, including that the ablation still lets the $100 charge
through.

Three things the phase turned up that were not on the list. The demo would have crashed on a
fresh Windows clone — cp1252 cannot encode `─`, `→` or `│` — so glyph selection now probes the
attached stream. Under `--scope gold` the preparatory `payments_list_methods` read is
**refused** where the compiled scope allows it — the blind author did not license
`READ:FINANCIAL` for that underspecified utterance — so the reference label reaches the same
prevented outcome by a stricter route. Not a defect, and not F-29; left visible. And
`couple-scopes`' pydantic serialization warning turned out to be two `model_copy(update=...)`
calls passing lists into tuple-typed fields — fixed, with all four output digests unchanged,
which is what makes it a lint fix rather than a result change.

**Nothing was measured, so `EXPERIMENTS.md` gains nothing.** No finding, no registered
prediction, no number. Two shared-code touches were made and both were shown neutral rather
than argued to be: the coupling fix reproduces its four output digests exactly, and
`ActionOutcome` gaining `ask_text` leaves `perclass-sonnet-s1__M0-consequential`'s committed
`report.json` and `report.md` byte identical on a fresh 621-episode replay.

Delivered: `agentfw demo` (+ `--scope`, `--scenario`, `--variant`, `--seed`, `--list`,
`--full`, `--brief`, `--no-color`), `LICENSE` (MIT, D-040), pyproject metadata and keywords,
a README **Run it** section with six runnable commands where there were none, and 34 new
tests.

*Exit criterion, met:* someone who has never seen the project can watch it refuse something in
under a minute, with no key.

Original plan follows.


Small, and it goes first so the repo is presentable from here onward regardless of what
happens to the rest of the plan.

- `agentfw demo` — replays one committed episode and prints the ALLOW / ASK / BLOCK trace with
  the monitor's own explanations. **Must work with no key**: the episodes are committed, and
  replay is already deterministic and free.
- `uv sync` works from a clean clone; a `LICENSE` exists; the repo has a description and topics.

*Exit:* someone who has never seen the project can watch it refuse something in under a minute.

### Phase 6 — the learned intent compiler (D-038)

The substance, and the first ML in the project. Baseline to beat is already measured and
published: **15.0% leakage / 100% retention at ~$6 per 207-utterance run.**

1. **Register the predictions before training anything.** Same discipline as E-00j and E-14.
   At minimum: where it fails (F-33's `docedit` cluster), whether TF-IDF matches the encoder,
   and whether leave-one-world-out collapses.
2. **Build and commit the dataset.** 293 blind-authored utterances over ~20 effect classes from
   `dev.yaml` + `heldout_v3.yaml`; extend via the generator, whose contested-class labels are
   structural and therefore free.
3. **Baselines in cost order: majority class → TF-IDF + logistic regression → fine-tuned small
   encoder.** The cheap baselines are not filler. **If TF-IDF matches the encoder, that is the
   finding**, and it is a more interesting one than a tuned number.
4. **Evaluate leave-one-world-out and dev/held-out**, because the utterances are
   template-generated and surface-form memorisation is the live risk (R-14 again).
5. **Wire it in as a non-structural signal** — D-006: may raise an ASK, may never grant — and
   **replay on the committed episodes** so the result is a verdict-level number and not only an
   F1. A scope-level score alone would repeat the mistake F-14 taught: *a compiler change is not
   an improvement until the replay says so.*

*Exit:* a table putting the learned compiler beside the prompted one on leakage, retention,
contrast and cost. **Either direction ships.** If a small encoder cannot do this, report the
error analysis and stop — do not grind on architectures (D-038).

*Optional follow-on, only if step 5 is decent:* a **cascade** — cheap local model handles the
confident cases, escalates the rest to the frontier compiler. Note for whoever picks this up:
this is *compiler routing* and is **not** the M0–M5 authority ladder that D-032 retired. Do not
conflate them; it needs its own decision entry.

### Phase 7 — presentation

Done *after* Phase 6, so it is done once rather than twice.

- Restructure `README.md`: what it is → GIF → headline number → quickstart → how it works →
  results. The current phase-by-phase narrative moves to `docs/RESEARCH_LOG.md`, where it is an
  asset for anyone who digs instead of a wall for everyone who does not.
- Keep exactly two result tables above the fold: the 2x2 and F-34's disposition table. They are
  the two that a non-specialist can read.

### Phase 8 — defensibility, then post

- The 10–15 questions someone will actually ask — *why a clustered bootstrap; what is D-006 and
  why does it constrain the design; walk me through a result that surprised you* — and where in
  the repo each answer lives. **Keep this file out of the repo**; it is preparation, not a
  deliverable.
- Then the LinkedIn post: the GIF and one number.

### Explicitly not in this plan

Phase 4's cost model (deferred, D-038), the paper (deferred; blocker is R-14), multi-agent,
memory poisoning, computer-use (out of scope by `PROJECT_SPEC.md` section 7), and any scenario
authoring beyond what Phase 6 needs. **Scope is defended, not expanded.**

---

## Phase 4 — Cost model, flow control, and full integration

**Re-scoped by D-034 and F-29 before it starts.** Two deliverables gained a specific,
measured requirement in Phase 3.5, and deliverable 0 is new:

0. **Decide something in the band D-034 reopened**, and measure the cheap options first: the
   *structural* fix (refuse a grant that its own open question contradicts — dismissed on dev
   evidence of 2 of 8, untested held out) and a *disagreement* ensemble across arms. Only if
   both fail does a calibrated `P(licensed)` earn its apparatus. The cascade and M1–M3 stay
   retired on D-032's cost argument, which E-11 did not touch.

Deliverables:
1. `policy/cost_model.py` — the expected-cost decision, `C_ask` sweep, per-effect
   `C_allow_harmful` from reversibility/externality/magnitude. **F-10 is its first measured
   requirement**; the compliance metric it optimises is unsound until F-29 is fixed.
2. `monitors/flow.py` — confidentiality lattice, declassification grants, sensitive-pattern
   ingestion labeling. **F-29 first**: the gate currently denies a licensed payment because an
   opaque local handle appears in an argument, and it does so only when that handle is at
   least `MIN_EVIDENCE_LEN` characters long.
3. ASK budget + fail-closed exhaustion (D-009); reviewer fatigue model.
4. **E-04: the ASK-budget sweep** — the headline trade-off curve, first version.
5. Full-system integration; all monitors live.

---

## Phase 5 — Benchmark build-out and experimental evaluation (COMPLETE, brought forward)

**Re-ordered ahead of Phase 4 by D-036**, because every quantity Phase 4 would optimise
against carried a ±23 pp interval that no amount of seeding narrows. **Sized by E-13 rather
than by the original estimate: 60 held-out core triples as a floor, 100 to settle D-034.**
The original Phase 0 target — "60–100 pairs", written before any episode had run — turned out
to be approximately what the power analysis demanded.

**All seven deliverables are done.** 60 core triples, 81 scenarios, 207 utterances, three
worlds, nine contested effect classes; gold scopes authored blind with the brief committed
first (D-033); a fresh undefended baseline (E-00j, 621/621 usable); E-11 and E-12 re-run at
N=60 (E-14). **Twelve registered predictions across the two runs and all twelve held.**

*The exit criterion.* E-14's prediction 30 was registered as the criterion on D-034 before any
call was made. No compiled arm reaches 0.0%; the best is **5.6% [1.1, 11.7]**, excluding zero.
**D-034 is confirmed on adequate power (D-037)** and Phase 4 proceeds with a real estimand.

*What Phase 5 changed that Phase 4 must not ignore.*

- **E-00i's 81.8% headline was wrong by 32 pp** and is superseded by E-00j's 49.4%. About
  13 pp of that is composition, and the rest small-sample noise.
- **F-32: the contested effect class explains an 87.5 pp spread; the domain explains 13.5 pp.**
  Any per-effect cost term must be fitted per class, not pooled.
- **F-33: the residual is six utterances, not a rate.** 33 of 60 leak under no arm. Size the
  cost model against the contested third, not against 5.6%.
- **F-34: `not_licensed` and "absent from the grant list" are different inputs** and the
  monitor already treats them differently. No ladder design should collapse them.
- **E-12 at N=60: the coupling rule is a substitute for the `per-class` prompt, not a
  complement**, and degrades the best arm. D-035's refusal to adopt is confirmed.
- **The interaction between prompt and model is unresolved.** Additive is refuted;
  multiplicative fits the point estimates on an interval of [0.21, 2.50]. N=60 sizes main
  effects, not interactions.

*What is deliberately not done.* The 100-triple target that D-036 named as the level needed to
settle D-034 *to the point of an interval excluding zero on every arm* — 60 was the floor and
it sufficed for the criterion as registered. Two suspect scenarios (F-33) are measured and
**not** repaired; they go in the next slice, fixed before anything is measured against them.
R-14 — Claude-authored scenarios, labels and compiler arms — is untouched and is now the
largest single risk to every number in this document.

Original plan follows.


## Phase 5 — Benchmark build-out and experimental evaluation (as planned)

Deliverables:
1. AF-Auth and AF-Inject scaled to full size (~120–200 and ~100+ scenarios), **dev/held-out
   split enforced**.
2. All baselines B-00…B-06 implemented, including B-04 (the strong injection firewall) and
   B-06 (confirm-every-write).
3. Attack tiers T1/T2/T3, including the pre-authorized-tools-only attack and ASK flooding.
4. AgentDojo adapter run.
5. All ablations.
6. **E-05 … E-09:** headline frontier, ablation table, adaptive-attack table, cost/latency
   table, per-model comparison. Everything with n>=3 seeds and bootstrap CIs.
7. Failure analysis: a hand-read sample of every error category.

**This is the longest phase. Budget accordingly.**

---

## Phase 6 — Visualization and developer experience

Deliverables:
1. Trace-replay dashboard over exported audit JSON: trajectory tree, per-action detail
   panel (scope, provenance evidence spans, effect, signals, cost-model inputs, verdict,
   explanation), attack/benign side-by-side.
2. Developer surface — pick **one** and do it well: a `@firewall.guard` decorator /
   `ToolRouter` wrapper for Python agents, plus a CLI to replay and inspect logs.
3. MCP proxy only if time remains.

---

## Phase 7 — Hardening, reproducibility, release

Deliverables: Docker/uv lockfile, one-command reproduction of every table, README with
structural claims and statistical claims clearly separated, architecture diagrams,
limitations section that actually lists the conceded threats, demo script, screenshots.

---

## Sequencing risks

- Phase 5 is where projects like this die (scenario authoring is slow). Mitigation: build
  the scenario *format* and the generator in Phase 1, so Phase 5 is scaling rather than
  inventing. **This mitigation failed and was repaired in Phase 3.5.** Having a generator was
  not the same as having the right one: it shipped with a single template producing *explicit
  pairs* while D-018 had re-centred the benchmark on *underspecified triples* in the same
  phase, and nothing forced a template to declare which shape it made. The held-out suite was
  therefore unable to exercise the phenomenon for two phases (D-031). The repair is
  structural — a template now declares its variants, and a validator rejects a three-variant
  af_auth template that has lost the a/c contrast — so the same failure cannot recur silently.
  **The transferable lesson: a mitigation that is a deliverable rather than a check is not a
  mitigation.**
- Phase 3 can absorb unlimited time. Mitigation: E-01/E-02/E-03 are defined up front with
  fixed deliverables; new model ideas go into `EXPERIMENTS.md` as backlog, not into scope.
