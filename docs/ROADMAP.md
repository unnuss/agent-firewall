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

## Phase 3.5 — Benchmark repair and held-out validation (NEXT)

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

## Phase 4 — Cost model, flow control, and full integration

Deliverables:
1. `policy/cost_model.py` — the expected-cost decision, `C_ask` sweep, per-effect
   `C_allow_harmful` from reversibility/externality/magnitude.
2. `monitors/flow.py` — confidentiality lattice, declassification grants, sensitive-pattern
   ingestion labeling.
3. ASK budget + fail-closed exhaustion (D-009); reviewer fatigue model.
4. **E-04: the ASK-budget sweep** — the headline trade-off curve, first version.
5. Full-system integration; all monitors live.

---

## Phase 5 — Benchmark build-out and experimental evaluation

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
  inventing.
- Phase 3 can absorb unlimited time. Mitigation: E-01/E-02/E-03 are defined up front with
  fixed deliverables; new model ideas go into `EXPERIMENTS.md` as backlog, not into scope.
