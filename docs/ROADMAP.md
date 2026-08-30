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

## Phase 3 — Intent compilation and the authorization model (the ML core)

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
