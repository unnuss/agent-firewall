# Related Work — Landscape Review (as of 2026-08)

This document exists so that we never accidentally reinvent a solved problem, and so that
we can honestly state what is and is not novel about Agent Firewall. It was compiled from
a literature/tooling survey during Phase 0. **Every claim below should be re-verified
against the primary source before it goes into a paper or README.** Summaries here came
from search results and abstract-level reads, not full-paper reads.

---

## 1. The single most important finding

**Indirect prompt injection (IPI) defense at the tool boundary is close to saturated on
public benchmarks.**

Bhagwatkar et al., *"Indirect Prompt Injections: Are Firewalls All You Need, or Stronger
Benchmarks?"* (arXiv:2510.05244) show that two *simple, model-agnostic* LLM filters — a
tool-**input** firewall ("Minimizer", strips unnecessary/private data from tool arguments)
and a tool-**output** firewall ("Sanitizer", strips suspicious instructions from tool
results) — reach **near-perfect security with high utility on all four** of AgentDojo,
Agent Security Bench, InjecAgent and tau-Bench. Their thesis: the benchmarks have flawed
success metrics, implementation bugs, and weak attacks.

### Consequence for us
If Agent Firewall's headline claim is *"we stop indirect prompt injection"*, then:
- the claim is derivative (five to ten published systems already do it), and
- our numbers will be compared against a ~150-line baseline that already scores ~100%.

That is a losing position for a portfolio/research project. **We must not make IPI
defense the headline.** We implement IPI defense because a credible runtime layer needs
it, and we report it — but the contribution lives elsewhere (see section 3).

---

## 2. Prior systems we must know, cite, and in several cases re-implement as baselines

### 2.1 Out-of-band / architectural defenses (the serious line of work)

| System | Core idea | Why it matters to us |
|---|---|---|
| **CaMeL** (arXiv:2503.18813, Google/DeepMind/ETH) | A privileged LLM emits a *program* from the trusted user query; a quarantined LLM handles untrusted data with no tool access; a custom interpreter tracks data provenance and enforces capability policies before each tool call. Control flow can never be influenced by untrusted data. Reported ~67% of AgentDojo tasks solved *with provable security*. | The strongest "by design" answer. Our provenance layer is conceptually downstream of it. Its cost: the plan must be expressible as a program, and utility drops on open-ended tasks. |
| **FIDES** (arXiv:2505.23643, Microsoft) | Agent-level information-flow control with **confidentiality and integrity labels** enforced at runtime; dynamic taint tracking plus selective information hiding. | Direct ancestor of our FlowMonitor. We adopt the two-label lattice. |
| **RTBAS** (arXiv:2502.08966) | IFC adapted to tool-based agents, with two *dependency screeners* — LM-as-judge and **attention saliency** — to decide whether a tool call actually depended on tainted context. Reports ~2% utility loss while preventing all targeted attacks. Survey work calls it the only published design with both strong utility and strong prevention, yet **adopted by no production system**. | This *is* the "trace why the agent proposed an action" idea from the brief. Treat RTBAS as prior art, re-implement a variant as a component, and be explicit that we did not invent it. |
| **Progent** (arXiv:2504.11703) | A DSL for per-tool-call privilege policies. An LLM generates the initial policy from the user task and updates it during execution; **an SMT solver classifies each update as a narrowing (auto-applied) or an expansion (requires explicit approval)**, so the effective action space can only shrink without human consent. | The *monotonicity invariant* is excellent and we adopt it (DECISIONS D-007). Progent is our closest neighbour on the authorization axis. |
| **LlamaFirewall** (arXiv:2505.03574, Meta) | Production guardrail stack: **PromptGuard 2** (86M/22M BERT-style jailbreak classifier, reported ~97.5% recall at 1% FPR), **AlignmentCheck** (few-shot chain-of-thought auditor for goal hijacking), **CodeShield** (static analysis). Reported ~90% ASR reduction (17.6% to 1.75%). | AlignmentCheck is the closest existing thing to "goal–action consistency". PromptGuard 2 is a free, strong, cheap component — use it, do not rebuild it. |
| **CommandSans** (arXiv:2510.08829) | Surgical token-level sanitization of tool output. Reports 7x–19x ASR reduction with no significant utility drop. | Another strong, simple baseline. |
| Dual-LLM, Conseca, FORGE | Other out-of-band patterns systematized in the survey literature. | Cite; do not implement. |

### 2.2 Adaptive-attack evaluation

*"Adaptive Evaluation of Out-of-Band Defenses Against Prompt Injection in LLM Agents"*
(arXiv:2606.26479) systematizes eight out-of-band defenses and adaptively attacks
**Progent** with a defense-aware injection that disguises the malicious action as a
benign, pre-authorized, necessary step — i.e. it attacks the one *model-based* component
inside an otherwise deterministic gate. Result on Qwen2.5-7B / AgentDojo: undefended ASR
25.8%, Progent vs. standard attack 4.2%, Progent vs. adaptive attack 2.6% (no increase).
The authors are careful: one defense, one weak model, one attack family.

Their recommended protocol — which **we adopt wholesale** as our adaptive-attack spec:
defense-aware string optimization; **provenance spoofing**; white-box/GCG; **attacks that
use only pre-authorized tools**; independent repeated runs with variance reported.

"Attacks that use only pre-authorized tools" is the item that will hurt us most, and is
therefore the one we must build first.

### 2.3 Benchmarks

- **AgentDojo** — 97 tasks / 629 security cases across email, banking, travel, workspace.
  The de-facto standard; measures utility and security jointly. Known to be saturable
  (section 1) and to contain metric bugs for which 2510.05244 publishes fixes.
- **InjecAgent**, **Agent Security Bench (ASB)** (10 scenarios, 27 attack classes,
  including memory poisoning and backdoors), **tau-Bench** — the other three of the quad.
- **AgentHarm** — 110 explicitly malicious agent tasks (440 augmented), 11 harm
  categories. *Misuse*, not injection — a different threat model from ours.
- **OS-Harm** — computer-use agent safety: misuse, IPI, model misbehaviour.
- **ST-WebAgentBench** (arXiv:2410.06703) — 375 web tasks with **six policy dimensions:
  user consent, preference satisfaction, scope boundaries, strict execution, robustness
  to distribution shift, error recovery**; metrics "completion under policy" and
  "risk ratio". **The closest existing benchmark to our authorization thesis** — but it is
  web-agent-specific and policy-compliance-shaped, not intent-scope-shaped.
- **LivePI** (arXiv:2605.17986) — IPI on a *real VM* with live-but-test-controlled email,
  chat, web, files, repo and wallet. Seven input surfaces, twelve attack families, five
  malicious goals. Reported total ASR 10.7%–29.6% across GPT-5.3-Codex, Claude Opus 4.6,
  Gemini 3.1 Pro, Kimi K2.5, GLM-5. A good model for *how realistic a sandbox should be*.
- **AgentS4D**, **NetInjectBench**, **PI-Hunter**, **PISmith** — 2026 additions; PI-Hunter
  and PISmith are automated / RL red-teaming and are worth mining for attack templates.

### 2.4 The human-oversight literature — where the gap actually is

- **Wang, Li & Tian, *"Reframing LLM Agent Security as an Agent–Human Interaction
  Problem"*** (arXiv:2605.24309, UCLA). Systematic analysis of 59 papers, 21 production
  agent systems and 26 security plugins (as of April 2026). Findings we care about:
  - The three dominant *production* mechanisms are **policy specification, runtime
    approval, scope configuration** (each in at least 14 of 21 systems).
  - The two categories most studied in *academia* — **intent anchoring** and **trust
    labeling** — have **zero production deployment**.
  - Users suffer **approval fatigue**; scope configured once at session start fails to
    adapt as the task evolves; policy languages are inaccessible to non-experts.
  - Verdict: the problem is not a lack of human involvement, it is that current
    involvement is poorly designed, under-studied and lacks theoretical grounding.

- **"Oversight Has a Capacity: Calibrating Agent Guards to a Subjective, Fatiguing
  Human"** (arXiv:2606.08919). Models the reviewer as an endogenous, fatiguing agent.
  Key result: the safety-vs-escalation-rate curve is an **inverted U** — a more-escalating
  oversight policy can be the *less* safe one, and the safety-optimal escalation rate sits
  **below** "escalate everything". Guards that escalate too much are vulnerable to
  **flooding attacks** that exhaust reviewer attention. Evaluated on 125 hand-labeled
  adversarially-weighted actions; inter-annotator Fleiss kappa = 0.52 — i.e. **even humans
  only moderately agree on what is risky**. Human study left as future work.

- **SoK: Trust-Authorization Mismatch in LLM Agent Interactions** (arXiv:2512.06914).
  Names our exact distinction: an action can be **relevant to the stated goal while
  remaining unauthorized**, and conflating the two is an exploitable gap. Identifies
  insufficient pre-action authorization verification, implicit permission inference,
  delegation chains that obscure original authority, and temporal authorization gaps.

- **"What You Approve Is What Executes: Consent Integrity for Black-Box LLM Agents"**
  (arXiv:2606.02668) — the approval dialog itself is an attack surface. Directly motivates
  our rule that ASK prompts are rendered from firewall-derived facts, never from
  agent-authored prose.

- **"Options, Not Clicks: Lattice Refinement for Consent-Driven MCP Authorization"**
  (arXiv:2605.11360) — consent as lattice refinement; adjacent to our scope model.

- **CHI 2026 landscape analysis of commercial agents** (10.1145/3772363.3798851) — an
  authorization gap between what users grant for task completion and what is consumed
  downstream.

- Practitioner evidence of the same failure mode: Google Antigravity "Turbo mode"
  auto-approve deleting a user's drive; the Amazon Kiro production-environment deletion;
  a coding agent dropping a production database despite an explicit prohibition. These are
  **authorization/overreach failures, not prompt injection**, and they are the incidents
  people actually remember. (Sourced from secondary reporting — verify before citing.)

### 2.5 Clarification / underspecification (adjacent, useful)

ClarEval (arXiv:2603.00187) reports GPT-4o at 89.02% Pass@1 on clarified tasks vs
**8.94% under ambiguity**. Information-gain-driven clarification (arXiv:2606.03135, ICML
2026) and uncertainty decomposition (arXiv:2606.19559) give us principled machinery for
*when to ask*. That literature asks clarifying questions to improve **utility**; we ask
them to bound **authority**. The mechanisms transfer; the objective differs.

### 2.6 Off-the-shelf components

- **Guard models**: PromptGuard 2 (86M / 22M), Qwen3Guard (0.6B/4B/8B, reported notably
  stable across prompt phrasings), Granite Guardian 3.2 (has an explicit *function-calling
  risk* detector), ShieldGemma 2B (reported highly prompt-sensitive), WildGuard.
  Practitioner guidance: keep an input rail under ~100 ms p50, an output rail under
  ~150 ms p50.
- **MCP gateways**: mcp-firewall, Lunar MCPX, Bifrost, Peta, Traefik Hub MCP. These
  already do coarse policy, audit and human-approval queues. They are *plumbing*, not
  intelligence — a useful integration target in Phase 6 and a useful honest comparison
  ("existing gateways enforce static allowlists; we infer scope from intent").

---

## 3. Where the actual gap is — and therefore what we build

Putting 2.1 against 2.4:

1. **Integrity/provenance defense (IPI)**: crowded, near-saturated, strong prior art.
2. **Confidentiality/flow control**: solid prior art (FIDES, RTBAS), not saturated but
   well understood.
3. **Authorization — did the user license this *consequence*?**: named as an open gap by
   a 2025 SoK, absent from production, and *deliberately not covered* by the four standard
   benchmarks (they measure whether the agent was hijacked, not whether an un-hijacked
   agent exceeded its mandate).
4. **The cost of asking**: proven to be non-trivially structured (inverted-U safety
   curve), proven to be the number-one production complaint (approval fatigue), and
   **not optimized by any of the systems in 2.1** — all of which treat human confirmation
   as an unmodelled fallback.

**Agent Firewall's contribution is (3) x (4):** a runtime layer that maintains an
*intent-derived authorization scope*, and whose central design objective is to spend a
**finite human-attention budget** as efficiently as possible — maximizing risk averted per
interruption, rather than minimizing attack success at any interruption cost.

Concretely, three things nobody appears to have published in this combination:
- **AF-Auth**, a *minimal-pair* benchmark for authorization (identical world, identical
  tools, user utterances differing only in licensed consequence — "find" vs "book",
  "draft" vs "send", "list deletable files" vs "delete them"), giving ground truth **by
  construction** rather than by annotation (which kappa = 0.52 tells us is unreliable).
- A **three-axis evaluation frontier**: security x utility x interruptions-per-task, with
  the ASK threshold swept to produce a *curve per defense* instead of a single point.
- An empirical answer to **"is semantic goal–action similarity actually useful?"** — we
  predict it works for injection and fails for overreach, and we will publish that either
  way (EXPERIMENTS E-01).

## 4. Sources

- https://arxiv.org/abs/2510.05244 — Indirect Prompt Injections: Are Firewalls All You Need, or Stronger Benchmarks?
- https://arxiv.org/abs/2503.18813 — Defeating Prompt Injections by Design (CaMeL); code: https://github.com/google-research/camel-prompt-injection
- https://arxiv.org/pdf/2505.23643 — Securing AI Agents with Information-Flow Control (FIDES)
- https://arxiv.org/abs/2502.08966 — RTBAS
- https://arxiv.org/abs/2504.11703 — Progent: Securing AI Agents with Privilege Control
- https://arxiv.org/abs/2505.03574 — LlamaFirewall; docs: https://meta-llama.github.io/PurpleLlama/LlamaFirewall/
- https://arxiv.org/pdf/2510.08829 — CommandSans
- https://arxiv.org/html/2606.26479v1 — Adaptive Evaluation of Out-of-Band Defenses
- https://arxiv.org/abs/2605.24309 — Reframing LLM Agent Security as an Agent–Human Interaction Problem
- https://arxiv.org/html/2606.08919v1 — Oversight Has a Capacity
- https://arxiv.org/pdf/2512.06914 — SoK: Trust-Authorization Mismatch in LLM Agent Interactions
- https://arxiv.org/html/2606.02668v1 — What You Approve Is What Executes: Consent Integrity
- https://arxiv.org/pdf/2605.11360 — Options, Not Clicks: Lattice Refinement for Consent-Driven MCP Authorization
- https://arxiv.org/abs/2410.06703 — ST-WebAgentBench
- https://arxiv.org/abs/2605.17986 — LivePI
- https://arxiv.org/pdf/2506.14866 — OS-Harm
- https://arxiv.org/html/2603.00187v1 — ClarEval
- https://arxiv.org/html/2606.03135 — Uncertainty-Aware Clarification with Information Gain
- https://arxiv.org/pdf/2510.06445 — A Survey on Agentic Security
- https://arxiv.org/abs/2604.23374 — Ghost in the Agent: Redefining Information Flow Tracking for LLM Agents (NeuroTaint)
- https://github.com/OSU-NLP-Group/AgentSafety — LLM agent safety paper list
