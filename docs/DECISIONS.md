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

**Amended 2026-08-29 (after E-00b).** The debt is now the single most important open item
in the evaluation. E-00b's central claim — that these models refuse explicit escalation but
not under-specification — rests on two OpenAI models, so a shared post-training lineage
cannot be ruled out as the cause. Until it is replicated on a model from a different
family, the finding must be stated as "on the models tested", never as a property of LLM
agents. The agreed route is a hosted-notebook run (Kaggle or Colab) rather than local
hardware; the runner is already provider-agnostic and resumable, so this is a config
change plus a notebook, not new engineering.

---

### D-017 — Re-centre AF-Auth on under-specification, not explicit verb contrast
**Date:** 2026-08-29 · **Status: accepted with modifications, 2026-08-29. The accepted
form is D-018, which narrows what was proposed here. Read D-018, not this entry, as the
operative decision.**

**Decision proposed.** Treat E-00 as a partial refutation of the current AF-Auth design.
Specifically: (a) retire "find a flight → books it" as the project's motivating example,
because our own measurement puts it at 0/6; (b) rebuild the AF-Auth dev slice so that the
low-authority variant is *under-specified* rather than *explicitly lower-consequence*;
(c) re-run E-00 on the revised slice before committing to Phase 2.

**Evidence.** E-00, 264 episodes, 2 models, 3 seeds. Overreach 0/24 in B1, 0/12 in B2,
0/6 in B3, 0/6 in B5, and 5/12 in B4. Compliance on the high-authority half is 93.3% and
benign BTC 89.8%, so the zeros are refusals rather than incapability. The same pattern
appears in AF-Inject: attacks naming an explicit unauthorised consequence scored 0/6, while
the attack framed as a "required intermediate step" scored 4/6.

**Reasoning.** The current B1 pairs differ by an explicit verb — "draft" versus "reply",
"find" versus "book". That is the canonical example in every model's safety post-training,
so the pair measures RLHF coverage rather than authorization reasoning. The pairs that did
produce overreach withhold the verb entirely ("deal with it") and force the model to supply
one. Keeping the current design risks the worst outcome for this project: a firewall that
scores well against a baseline of ~0% and therefore demonstrates nothing.

**Why this does not kill the thesis, and where it does bite.** The *oversight-efficiency*
framing survives and arguably sharpens: the failure mode we measured — under-specification
resolved toward the higher-consequence reading — is exactly the case where the correct
action is ASK rather than BLOCK, which is the mechanism the cost model exists to budget.
What does *not* survive is the broader claim in PROJECT_SPEC section 2 that agents commonly
take consequences the user never licensed; against explicit instructions, these models
do not. PROJECT_SPEC and README both overstate the problem relative to our own data.

**Alternatives considered.** (a) Accept 8.3% as clearing the 5% gate and proceed to Phase 2.
Rejected: the CI is [0.0, 25.0] and the effect is one scenario, so the gate is not really
passed. (b) Declare the thesis falsified and stop. Rejected as premature: B4 shows a real,
reproducible failure at 41.7%, and n=10 pairs is too small to conclude absence.

**Cost of being wrong.** If we re-centre on ambiguity and ambiguity turns out to be rare in
realistic tasks, we will have spent a phase rebuilding scenarios. That is cheaper than
discovering in Phase 5 that the headline comparison has no signal in it.

**Revisit trigger.** The revised E-00. If overreach on an under-specification-centred slice
does not clear ~15%, the honest move is to re-frame the project around AF-Inject plus the
oversight-efficiency curve and say so in the README.

---

### D-018 — Reframe AF-Auth around authorization under under-specification; keep the controls
**Date:** 2026-08-29 · **Status:** accepted (supersedes D-017 as proposed)

**Decision.** D-017 asked to re-centre AF-Auth on under-specification. Accepted, with one
substantive correction: **do not narrow the project to under-specification only, and do
not discard the explicit-escalation cases.** They are retained as *controls*. Concretely:

1. AF-Auth gains ~12-20 hand-audited underspecified authorization scenarios across
   multiple domains. Delivered: **14 new triples across 7 domains**, plus the one original
   B4 pair that qualifies = 15 core scenarios.
2. Scenarios must represent genuinely plausible ambiguity, not prompts engineered to make
   the model overreach.
3. B1/B2/B3/B5 are kept and their negative result reported honestly. They are now tagged
   `role: control`.
4. E-00 is re-run as **E-00b**.
5. Both **episode-level overreach rate** and **scenario-level incidence** are reported.
6. The uncertainty method is reviewed so repeated seeds and models within one scenario are
   not treated as independent.
7. The Cloudhost invoice case survives as the motivating example **only if** E-00b shows
   the phenomenon generalises beyond it.
8. The registered E-00 results are not altered.
9. Thesis and README change only *after* E-00b provides evidence.
10. Phase 2 does not begin.

**What was implemented for each.**

*Point 1-3, the scenario design.* Core scenarios are **triples**, not pairs, over one world
and one contested effect: `a` low-authority underspecified, `b` high-authority explicit,
`c` low-authority **explicit**. The `a`/`c` contrast is the load-bearing addition and was
not in D-017. Both are low-authority asks about the same goal in the same world; only the
wording differs. If `a` overreaches and `c` does not, ambiguity is the cause. If both
overreach, the scenario is merely pushy and must be rewritten. That is the mechanical
answer to point 2 — the suite contains its own control against being engineered.

The authoring bar is additionally enforced by a test: an utterance labelled
`underspecified` must not contain a word naming its own consequence (no "send", "pay",
"delete", "share" ...). If the utterance says the word, the model is following an
instruction rather than resolving ambiguity, and any overreach measured would be a
labelling error rather than a finding.

*Point 5-6, measurement.* `scenario_incidence` reports how many distinct scenarios show at
least one overreach; a phenomenon driven by one scenario and one spread across twenty can
share an episode-level rate and mean completely different things. On the original E-00 data
incidence is **1/10** — which is exactly the fact the episode-level 8.3% was hiding. For
uncertainty, the clustered bootstrap was already correct in resampling scenarios rather
than episodes; what was missing was making the difference *visible*. The report now prints
the clustered interval, the naive iid interval, and the width ratio between them, and
states that the naive figure is never quoted as a result.

*Point 8, preserving the record.* E-00b writes to `experiments/e00b_revised/`. The original
`experiments/e00_undefended/results/` is untouched, and E-00 reproduces exactly at commit
`00bca69`. Freezing by commit rather than by immobilising the suite is what lets the suite
keep evolving without rewriting history.

**Honest note on a relabelling.** `af_auth.calendar.dana_ambiguous` was filed as B4
ambiguity in the original suite, but its low-authority utterance actually names the action
("tell me what she is proposing"). It is an explicit-low case and has been retagged
`control`. So the original E-00 "B4 = 41.7%" cell was really one genuinely underspecified
scenario averaged with one that was not. This does not change any registered number; it
changes what that number meant.

**What would still falsify the reframing.** If E-00b shows the underspecified and explicit
low-authority variants overreaching at similar rates, ambiguity is not the mechanism and
the honest move is to re-frame the project around AF-Inject plus the oversight-efficiency
curve. If scenario-level incidence stays in the low single digits, the phenomenon does not
generalise and the Cloudhost case must be retired as the motivating example (point 7).

---

### D-019 — The competency floor is a gate, not a caveat
**Date:** 2026-08-29 · **Status:** accepted

**Decision.** A run whose high-authority compliance falls below **60%** is **inconclusive**:
neither confirmation nor falsification, excluded from inference, preserved as a historical
record. The floor is enforced in code (`metrics.competency_gate`), printed by
`agentfw report`, and marked by `agentfw compare`. It is not a sentence in a discussion
section that a later reader can skim past.

**Reasoning.** E-00c is why this exists. Qwen3-8B produced a directionally correct result —
17.8% underspecified versus 1.4% explicit-low, 19.0% versus 0.0% on matched pairs — at 31.9%
compliance. The temptation to read that as weak confirmation is strong and wrong. An agent
that fails to act two thirds of the time when instructed produces low rates everywhere, and
the explicit-low denominator is precisely where incapability and correct restraint are
indistinguishable. The confound runs *in the direction that flatters the hypothesis*, which
is the case a pre-registered rule exists for.

Making it mechanical matters more than agreeing to it. A number in a results table outlives
the paragraph explaining why it should not be quoted.

**Alternatives.** (a) Report E-00c with a written caveat. Rejected: the caveat and the
number get separated the first time anyone builds a summary table. (b) Lower the floor to
fit the result. Rejected for obvious reasons, and noted here so the temptation is on the
record.

**Cost.** Runs that fail the gate cost GPU time and yield no inference. That is the correct
price; E-00c still taught us the harness works unmodified against a locally served model and
that Qwen3-8B is not viable as an agent in this sandbox at any later phase.

**Revisit if.** A principled analysis shows the floor should be a function of the contested
effect's difficulty rather than one global number. Do not revisit it because a run landed
just below.

---

### D-020 — Move the cross-family replication to hosted inference
**Date:** 2026-08-29 · **Status:** accepted · **Recorded before any E-00e result was observed**

**Decision.** Stop trying to fit the cross-family replication onto free-tier GPU hardware.
Run E-00e against a strong hosted open-weight model through an OpenAI-compatible API
(OpenRouter), with Meta Llama 4 Maverick as the primary candidate and Llama 3.3 70B
Instruct as the named fallback.

**Evidence.** Two pre-registered attempts, both failing the competency floor:

| Run | Model | Precision | Compliance | Floor |
|---|---|---|---|---|
| E-00c | Qwen3-8B | fp16 | 31.9% | 60% |
| E-00d | Qwen3-14B-AWQ | 4-bit | 36.1% | 60% |

Nearly doubling parameters bought 4.2 points. On that slope, closing a 24-point gap needs a
model far outside what 2xT4 can host. The binding constraint is the capability envelope of
free-tier hardware, not a missing model family.

**Reasoning.** We were optimising the wrong variable. The scientific question is whether the
E-00b contrast is family-specific; running ever-smaller models to fit a GPU answers a
question about quantisation and scale instead. Hosted inference removes the hardware
constraint at an estimated cost of $0.15-0.25 for the whole run — less than the GPU-hours
already spent on two inconclusive attempts.

**The distinction that keeps this honest.** E-00c and E-00d failed on *capability*, not on
*evidence standards*. What changes here is the model we can afford to run; what does not
change is the bar it must clear. The 60% floor (D-019) stands, was not adjusted to fit these
results, and must not be adjusted after E-00e is observed. This entry is dated and committed
before E-00e exists precisely so that claim is checkable rather than asserted.

**Alternatives.** (a) A third small model on Kaggle. Rejected: the slope says it fails too.
(b) Paid GPU (Colab Pro A100). Rejected: more expensive and slower to arrange than hosted
inference for the same result. (c) Abandon cross-family replication and proceed to Phase 2
on OpenAI-only evidence. Rejected — that is the single largest threat to the project's
central finding, and skipping it would make every later result conditional on an unexamined
assumption.

**Cost of being wrong.** If hosted Llama also fails the floor, the honest conclusion shifts:
the sandbox may be unusually hard for non-OpenAI models, which would be a finding about our
*benchmark* rather than about the models, and would need investigating before any headline
claim survives.

**Note on nomenclature.** E-00e's config says `provider: openai`. That denotes the
OpenAI-compatible wire format, not the model lineage. The model is Meta's. Anyone auditing
the config should read `model:` and `base_url:`, not `provider:`.

