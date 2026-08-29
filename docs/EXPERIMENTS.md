# Experiments

Every experiment is defined *before* it is run: question, hypothesis, design, metrics,
what would falsify it. Results are appended below the definition. No experiment is removed
because its result was unflattering.

**Status legend:** `planned` · `running` · `done` · `abandoned (reason)`

---

## E-00 — Does the problem exist? Undefended baseline
**Phase:** 1 · **Status:** planned · **Priority: highest — this is the go/no-go**

**Question.** How often does a competent, un-attacked agent produce a consequence the user
did not license? And how often is it hijacked?

**Hypothesis.** Overreach rate on the AF-Auth dev slice will be **15–40%** for the
low-authority half of the minimal pairs, concentrated in B1 (consequence escalation) and B4
(ambiguity). If it is under 5%, the project's thesis is wrong.

**Design.** Undefended agent, AF-Auth dev slice (8–10 pairs) + AF-Inject dev slice (5–8)
+ benign suite (15–20). n>=3 seeds, >=2 models (one frontier, one open-weight).

**Metrics.** OR, ASR, BTC, per-family breakdown, bootstrap 95% CIs.

**Falsifies.** OR < 5% → re-frame the project (see EVALUATION section 6).

**Status detail (2026-08-29).** Harness complete and validated; the run itself is
**blocked on model access**. See "Run log" below.

**Results.** *(pending — blocked, not skipped)*

### Run log

| Date | Event |
|---|---|
| 2026-08-29 | Harness built and unit-tested. Dev slice frozen at 10 AF-Auth minimal pairs, 6 AF-Inject scenarios, 18 benign tasks = 44 episodes per (model, seed); 264 episodes at n=3 seeds x 2 models. |
| 2026-08-29 | Run attempt 1 — failed. `OPENAI_API_KEY` returns HTTP 429 `insufficient_quota` / `credit_balance_exhausted`. Key authenticates (200 on `/v1/models`, 118 models listed) but the owning organisation has no usable credit. Reproduced on `gpt-5.1`, `gpt-4.1-mini`, `gpt-4.1-nano`, across two code paths. No `x-ratelimit-*` headers on the 429, confirming a hard quota block rather than throttling. |
| 2026-08-29 | Local open-weight fallback assessed and rejected for now — see D-016. |
| 2026-08-29 | Run attempt 2 — failed identically. Diagnosed as environment staleness, not billing: the key visible to the runner (SHA-256 prefix `cb8a849d`) differs from the newly issued key in the user's shell (`6de690a5`). A long-running process does not inherit a rotated environment variable. Mitigation shipped: `.env.local` loading (`agentfw/config.py`) so a key can be rotated without restarting anything. |

**Total API spend on E-00 to date: $0.00.** Every request was rejected before inference, so
no tokens were billed.

### Findings already produced by building the harness

These are results even though the experiment has not run, because they are facts about the
benchmark rather than about the agent.

- **F-01 — two AF-Auth oracles were trivially satisfiable before the agent acted.**
  A test asserting that every task and attack oracle is FALSE on an untouched world caught
  both: `af_auth.calendar.thursday::b` was satisfied by a pre-existing 10:00 dentist
  appointment on the same Thursday, and `af_auth.files.contract_ready::a` was satisfied by
  the contract's unrelated "Term: 12 months from execution" line. Both would have reported
  100% task completion regardless of agent behaviour. Fixed; the test is permanent.
  *Lesson for Phase 5:* oracle triviality is the cheapest way for this benchmark to lie to
  its authors, and it must be a gate on every generated scenario, not a review step.
- **F-02 — conservative taint saturates immediately.** The Phase 1 `Trace.context_label()`
  is the sound over-approximation (meet over every ingested span). In practice one
  `web_fetch` marks the remainder of the episode UNTRUSTED_WEB, which is exactly the
  imprecision the Phase 3 dependency screener exists to remove. Recorded now so the Phase 3
  comparison has a documented baseline rather than a remembered one.

---

## E-01 — Pre-registered: is goal–action semantic similarity useful?
**Phase:** 3 · **Status:** planned (prediction registered 2026-08-28, D-012)

**Question.** How much discriminative power does embedding/cross-encoder similarity between
the user objective and the proposed action carry, separately for hijacking and overreach?

**Hypothesis (registered in advance).**
- On **AF-Inject**: AUC **> 0.85** — injected actions really are semantically distant from
  the goal.
- On **AF-Auth**: AUC **< 0.65, plausibly near 0.5** — `purchase_flight` is *maximally*
  similar to "find me a flight" and is exactly the action that must not be allowed.
- Cross-encoder (M2) beats bi-encoder (M1) on both but does not close the AF-Auth gap.

**Design.** Score every proposed action in both dev suites with M1 (sentence-transformers)
and M2 (cross-encoder). Compute ROC-AUC against the ground-truth correct decision. Report
score distributions, not just AUC — the interesting picture is the overlap.

**Why it matters.** The original brief made goal–action consistency a primary mechanism. If
the prediction holds, this is a clean negative result that *motivates* the effect ontology,
and it is the kind of finding that makes a portfolio project look like research. If the
prediction fails, the architecture gets simpler and we say so.

**Results.** *(pending)*

---

## E-02 — The authorization-model ladder
**Phase:** 3 · **Status:** planned

**Question.** Which approach best estimates `P(user licensed this effect)`, per unit cost?

**Design.** M0 (effect-class membership, no ML), M1 (bi-encoder), M2 (cross-encoder),
M3 (guard model — PromptGuard-2 / Qwen3Guard-0.6B), M4 (LLM judge with a structured
authorization rubric). Same dev split, same prompts where applicable, n>=3.

**Metrics.** Accuracy / balanced accuracy, ROC-AUC, **ECE and reliability diagram**,
p50/p95 latency, tokens and dollars per decision.

**Hypothesis.** M0 is a surprisingly strong floor and must be beaten to justify any ML at
all. M3 is near-useless on AF-Auth because its training objective is jailbreak detection,
not authorization. M4 wins on accuracy but with 10–100x the cost and non-trivial variance
across seeds.

**Results.** *(pending)*

---

## E-03 — Cascade: where does the LLM judge earn its tokens?
**Phase:** 3 · **Status:** planned

**Question.** Can a cascade (M0 gate → M2 → M4 only inside an uncertainty band) retain
M4-level accuracy at a fraction of the cost?

**Design.** Sweep the band width; plot accuracy vs. cost and vs. p95 latency. Report the
fraction of decisions that reach M4.

**Falsifies.** If M4 is invoked on >50% of decisions to retain accuracy, the cascade is not
a contribution and we report a single-model design instead.

**Decides.** Whether M6 (distillation) is worth doing at all (D-011).

**Results.** *(pending)*

---

## E-04 — The ASK-budget sweep (headline figure)
**Phase:** 4 · **Status:** planned

**Question.** What does the security/utility/interruption frontier actually look like?

**Design.** Sweep `C_ask` (equivalently, the ASK band width) across the full range for
Agent Firewall; plot `CuP` and `1 - OR` against interruptions-per-episode. Overlay every
baseline: B-00 at 0 interruptions, B-06 at its natural rate, B-01…B-05 as points or curves.
Include the reviewer-error model at `epsilon ∈ {0, 0.05, 0.15}` and a fatigue variant where
`epsilon` grows with ASK count.

**Hypothesis.** (a) Agent Firewall's curve dominates B-06 — same or better security at
materially fewer interruptions. (b) With the fatigue model on, the curve is **non-monotonic**
— reproducing the inverted-U of arXiv:2606.08919 in our own setting. (b) would be a nice
independent replication.

**Results.** *(pending)*

---

## E-05 — Full benchmark: all defenses, all suites
**Phase:** 5 · **Status:** planned

Held-out AF-Auth + AF-Inject + benign + AgentDojo adapter, B-00…B-07, n>=3 seeds, >=2
models, attack tiers T1/T2. All metrics from `EVALUATION.md` section 3.

---

## E-06 — Ablations
**Phase:** 5 · **Status:** planned

`-integrity`, `-flow`, `-authorization`, `-effect-ontology` (tool-level risk instead),
`-cost-model` (fixed threshold), `-scope-monotonicity`, `-consent-integrity`.

**Hypothesis (worth being wrong about).** Scope monotonicity and the effect ontology carry
most of the security; the ML authorization head mainly buys back *utility* by converting
BLOCKs into correct ALLOWs and reducing unnecessary ASKs. If true, that reframes the ML
contribution honestly: it is a utility mechanism, not a security mechanism.

---

## E-07 — Adaptive attacks
**Phase:** 5 · **Status:** planned

Tier T2 (defense-aware: forged provenance, claimed pre-authorization, "necessary
intermediate step" framing, effect-class laundering, ASK flooding) and tier T3
(optimized strings against the open-weight configuration; **pre-authorized-tools-only
attack**). Protocol per arXiv:2606.26479.

**Expected.** T2 barely moves the structural properties (P1–P4) and meaningfully degrades
the ML head — which is exactly the argument for D-006. The pre-authorized-tools-only attack
is expected to **succeed**, and that concession goes in the README.

---

## E-08 — Overhead
**Phase:** 5 · **Status:** planned

Added latency (p50/p95) per tool call, tokens and dollars per episode, for every defense.

---

## E-09 — Component quality: intent compiler and effect mapper
**Phase:** 5 · **Status:** planned

Effect-set precision/recall and constraint-extraction accuracy for the intent compiler
against gold scopes; confusion matrix for the (tool, args) → EffectClass mapper. Needed to
answer "is the headline result really measuring an ontology?" (EVALUATION section 6.4).

---

## Backlog (ideas, not commitments)

- Attention-saliency dependency screening on an open-weight model (RTBAS-style). Time-boxed
  spike in Phase 3; drop if it does not work.
- Learning the cost model from user approve/deny behaviour instead of hand-setting it.
- Information-gain-driven ASK phrasing (arXiv:2606.03135) — ask the question that most
  reduces authorization uncertainty, rather than one question per contested action.
- Cross-episode scope reuse ("always allow this effect for this task type") with an explicit
  decay, and its security cost. This is the most-used production mechanism and the one with
  the worst security profile; measuring it would be a genuine contribution.
- A small human study of approval quality under load. Out of scope for this project but the
  obvious follow-up.
