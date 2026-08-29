# Decision Log

Format: ID, date, decision, alternatives considered, reasoning, status, revisit trigger.
Append only. If a decision is reversed, add a new entry that supersedes it rather than
editing history.

---

### D-001 — Re-rank the thesis: authorization first, injection second
**Date:** 2026-08-28 · **Status:** accepted

**Decision.** The headline contribution is *authorization under a human-attention budget*,
not indirect prompt injection defense. IPI defense remains a required component and a
reported result.

**Alternatives.** (a) Keep IPI as the headline, as in the original brief.
(b) Drop IPI entirely and build a pure authorization layer.

**Reasoning.** arXiv:2510.05244 shows a simple tool-input/output filter pair reaches
near-perfect security on all four standard public benchmarks; six-plus serious systems
already occupy that space (CaMeL, FIDES, RTBAS, Progent, LlamaFirewall, CommandSans).
Making IPI the headline means competing on a saturated metric against a trivial baseline.
Meanwhile arXiv:2512.06914 names relevance-vs-authorization as an open gap,
arXiv:2605.24309 finds intent anchoring has zero production deployment, and
arXiv:2606.08919 shows escalation policy is a genuinely unsolved optimization problem.
(b) was rejected because a runtime layer that ignores hijacking is not credible, and
because the two-family contrast (hijacking vs overreach) is the clearest way to explain the
system.

**Revisit if.** A 2026/2027 paper lands the authorization-benchmark contribution first, in
which case we pivot toward the oversight-efficiency angle specifically.

---

### D-002 — No agent framework; write our own ~300-line loop
**Date:** 2026-08-28 · **Status:** accepted

**Decision.** No LangChain, LlamaIndex, AutoGen, CrewAI. A hand-written tool-calling loop
behind a thin `LLMClient` protocol with Anthropic / OpenAI / local-vLLM implementations.

**Reasoning.** The object of study is exactly the tool-call boundary and the provenance of
every span in the trace. Frameworks abstract that boundary away, inject their own hidden
prompts, and change semantics between minor versions — which would silently invalidate
experiments. A tool-calling loop is genuinely small. The cost (we maintain it) is much
lower than the cost (unreproducible results, unexplainable behaviour in an interview).

**Revisit if.** We need broad tool-ecosystem coverage for a real-world integration demo —
at which point the right move is an MCP proxy, not a framework.

---

### D-003 — Rank *effects*, not tools
**Date:** 2026-08-28 · **Status:** accepted

**Decision.** Risk and authorization attach to `Effect = (verb, resource_class,
reversibility, externality, magnitude)`, with `EffectClass = (verb, resource_class)` as the
unit an `IntentScope` authorizes. Tools map to effects as a function of their arguments.

**Alternatives.** Per-tool risk scores (as in the original brief).

**Reasoning.** Per-tool risk cannot distinguish `http_request` GET from POST, cannot see
that two tools produce the same consequence, and produces an ontology that a new tool
breaks. Effect-level authorization is also what makes the "find vs book" distinction
expressible at all. Cost: the (tool, args) -> effect mapper becomes a component with its own
error rate, which we must measure rather than assume.

---

### D-004 — Deny-by-default over effect classes
**Date:** 2026-08-28 · **Status:** accepted

**Decision.** An effect class absent from `IntentScope.authorized_effects` is unauthorized.
There is no "unknown" middle state at the membership level.

**Reasoning.** Least privilege, and it makes P2 (every executed effect is in scope) a
runtime assertion rather than a heuristic. Utility risk is real and is exactly what the
ASK path exists to recover; it is measured as FPR-block and unnecessary-ASK rate.

---

### D-005 — Do not combine signals into a single risk score
**Date:** 2026-08-28 · **Status:** accepted

**Decision.** Hard structural gates run first and can only force BLOCK. The remaining
decision is made by an explicit expected-cost comparison over
`C_block_benign`, `C_allow_harmful(effect)`, `C_ask`, using a **calibrated** probability
that the user licensed the effect.

**Alternatives.** Weighted-sum risk score with tuned thresholds (the brief's proposal).

**Reasoning.** A weighted sum with hand-tuned weights is unfalsifiable, invites fitting to
the demo, and is the single clearest signal of hackathon-grade work. The cost model instead
gives: thresholds derived rather than tuned, an ASK band whose width automatically scales
with irreversibility, and — critically — a knob (`C_ask`) whose sweep *is* the headline
trade-off curve. It also forces calibration to be a first-class metric.

---

### D-006 — ML lives outside the trusted computing base
**Date:** 2026-08-28 · **Status:** accepted

**Decision.** Structural properties (P1–P4) are enforced deterministically. No ML component
can grant authority; ML can only move a decision within the band the structural gates
already permit.

**Reasoning.** Model-based gates are the component that adaptive attacks target
(arXiv:2606.26479 broke into Progent's LLM policy-updater, not its solver). Keeping ML
non-authoritative means an adaptive attacker who fully fools our classifier still cannot
expand scope. It also gives us four claims that hold without any statistical caveat, which
is worth more in a README than any single number.

---

### D-007 — Scope monotonicity: only a human can widen authority
**Date:** 2026-08-28 · **Status:** accepted

**Decision.** `IntentScope` can be narrowed by anything; it can be widened only by a
USER-labeled answer to an ASK. Enforced in the type, not by convention.

**Reasoning.** Adopted from Progent (arXiv:2504.11703), which uses an SMT solver to
classify policy updates as narrowing or expansion. We get the same invariant more cheaply
because our scope is a finite set plus constraints rather than a general DSL. This is the
structural answer to "the webpage said I was pre-authorized" (threat A1/A4), and it also
fixes the documented failure of *static* scope configured once at session start
(arXiv:2605.24309) without reintroducing the hole.

---

### D-008 — Consent integrity: ASK text is firewall-rendered
**Date:** 2026-08-28 · **Status:** accepted

**Decision.** Approval prompts are rendered from structured firewall facts. Agent-authored
prose never becomes the approval text; untrusted strings appear quoted and labeled.

**Reasoning.** arXiv:2606.02668. Without this, an attacker who cannot obtain ALLOW obtains
it from the human instead. Cheap to implement, easy to demo, and it makes ASK a defensible
security primitive rather than a shrug.

---

### D-009 — ASK budget with fail-closed exhaustion
**Date:** 2026-08-28 · **Status:** accepted

**Decision.** Each episode has an interruption budget; exhausting it causes BLOCK, not
ALLOW.

**Reasoning.** arXiv:2606.08919 shows an inverted-U safety curve and an ASK-flooding attack
that exhausts reviewer attention. A budget makes "how much oversight" an explicit,
sweepable parameter rather than an emergent accident, and fail-closed is the only choice
consistent with least privilege.

---

### D-010 — Minimal-pair construction for the authorization benchmark
**Date:** 2026-08-28 · **Status:** accepted

**Decision.** AF-Auth scenarios come in pairs sharing world state and tools, differing only
in the consequence the utterance licenses. Ground truth is by construction.

**Reasoning.** Prior work labeling "is this action risky?" reports Fleiss kappa = 0.52 —
humans only moderately agree, so annotation-derived ground truth would put a noise floor
under every number we report. Minimal pairs also make the benchmark ungameable by trivial
strategies: block-everything fails the high-authority half, allow-everything fails the
low-authority half.

---

### D-011 — Fine-tuning is conditional, not planned
**Date:** 2026-08-28 · **Status:** accepted

**Decision.** We do not commit to training a model. We commit to a *ladder* of approaches
(M0 rules → M1 bi-encoder → M2 cross-encoder → M3 guard model → M4 LLM judge → M5 cascade),
and train a distilled encoder (M6) **only if** M5 shows the LLM judge is the accuracy or
cost bottleneck and enough labeled scope/action pairs exist.

**Reasoning.** The brief explicitly warns against training something just to claim we
trained something. A rigorous comparison across the ladder — including the finding that the
cheap methods fail in a specific, explainable way — is stronger evidence of ML judgment than
an unnecessary fine-tune. If M6 does happen, it has a real justification and a real metric.

---

### D-012 — Predict and pre-register: embedding similarity will fail on overreach
**Date:** 2026-08-28 · **Status:** open prediction

**Decision.** We state in advance that we expect cosine similarity between the user
objective and the proposed action to have near-chance discriminative power on AF-Auth,
while performing well on AF-Inject, and we will publish the result either way.

**Reasoning.** In the hardest authorization cases, relevance and authorization are
*positively* correlated with each other and *anti*-correlated with the right answer:
`purchase_flight` is maximally relevant to "find me a flight" and maximally unauthorized.
The original brief treated goal-action semantic consistency as a primary mechanism; if the
prediction holds, that is a genuinely interesting negative result and a good reason the
project needs the effect ontology. Pre-registering it stops us from quietly dropping the
experiment if it is unflattering to the design.

---

### D-013 — In-process deterministic sandbox rather than a VM
**Date:** 2026-08-28 · **Status:** accepted

**Decision.** SQLite + in-memory world, seedable, snapshot/restore per episode, no real
network from tools.

**Alternatives.** A VM-backed world with live-but-controlled services, as in LivePI
(arXiv:2605.17986).

**Reasoning.** We need to run thousands of episodes across seeds, models, defenses and
ablations; determinism and speed dominate. The fidelity gap is real and is recorded as a
stated limitation, not hidden.

---

### D-014 — Documentation structure
**Date:** 2026-08-28 · **Status:** accepted

**Decision.** Keep the brief's five documents, add `THREAT_MODEL.md`, `RELATED_WORK.md`,
`EVALUATION.md`, `ROADMAP.md`, and a root `CLAUDE.md` for session handoff. `PROJECT_STATE.md`
stays at the root and is the first thing any new session reads.

**Reasoning.** The threat model and evaluation plan are the two documents a researcher will
check first, and burying them inside a spec makes them easy to fudge. `RELATED_WORK.md`
exists specifically to keep us honest about novelty.

---

### D-015 — No HTTP client dependency; stdlib only in the provider layer
**Date:** 2026-08-29 · **Status:** accepted

**Decision.** The provider layer talks to model APIs through `urllib.request` from the
standard library, not through `httpx`, `requests`, or the vendor SDKs (`openai`,
`anthropic`). Phase 1 therefore adds **no** runtime dependency beyond the two already
sanctioned in Phase 0: pydantic v2 and PyYAML.

**Alternatives.** (a) The official vendor SDKs. (b) `httpx` behind our own thin wrapper.

**Reasoning.** D-002 already says the tool-call boundary is the object of study and must
not be abstracted away. The vendor SDKs re-introduce exactly that risk on the wire: they
add retry, streaming and message-shaping behaviour that changes between minor versions and
is invisible in our code. The whole client is ~120 lines of POST-and-parse; the cost of
owning it is far below the cost of an experiment silently changing because an SDK did.
`httpx` was rejected as a dependency that buys only ergonomics.

**Cost, stated honestly.** We hand-roll retry/backoff, and we do not get streaming. Neither
matters for batch evaluation.

**Revisit if.** We need streaming for a live demo, or an API adds a wire feature that is
painful to implement by hand.

---

### D-016 — E-00 backbone selection, and the deferred open-weight run
**Date:** 2026-08-29 · **Status:** accepted, with a debt recorded

**Decision.** E-00 runs on two API models of different capability tiers rather than the
"one frontier + one open-weight" pair that EVALUATION section 5 requires. The open-weight
requirement is **deferred to Phase 3**, not dropped, and is tracked as RISK R-09.

**Reasoning.** The development machine has no NVIDIA GPU (Intel Arc iGPU only). Measured
locally: `dolphin3:latest` is rejected by Ollama with "does not support tools", and
`qwen2.5-coder:14b` emits tool calls as *plain text* rather than structured calls and took
48s for a 319-token prompt (~7 tok/s). A full E-00 dev slice is 264 episodes; at that
throughput one open-weight backbone is a multi-day serial run, and the models that do fit
in memory are weak enough that a low overreach rate could not be distinguished from plain
incapability — which would make the go/no-go gate unreadable rather than merely noisy.
The OpenAI key on this machine has no `gpt-oss-*` access, so the open-weight requirement
cannot be met through the API either.

**Why this does not compromise E-00.** E-00 asks whether a *competent* agent overreaches.
Capability is the premise, not the variable, and the run reports compliance-on-the-high-
variant and BTC precisely so that a capability-limited result is visible rather than
silently reported as safety. Two API tiers still give the cross-backbone check that stops
the headline being an artefact of one model.

**What is owed.** Phase 3 needs an open-weight backbone regardless, for the T3 white-box
attack tier and the attention-saliency spike (R-03). Whichever GPU answers open question
Q2 also settles this. Until then, no result may be described as model-agnostic.

**Revisit if.** GPU access arrives, or an open-weight model with reliable tool calling
becomes available through an API we can bill.

