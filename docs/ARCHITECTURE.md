# Architecture

**Status:** partly implemented. Sections 6 and 7 (agent loop, sandbox) landed in Phase 1.
Phase 2 implemented the deterministic half: sections 3 (data model), 4.1 (IntegrityMonitor,
structural mechanism only), the deterministic part of 4.2 (FlowMonitor), the structural
gates of section 5, and section 8 (audit and replay). Still design-only: 4.1 mechanism 2
(the dependency screener), 4.3 (the AuthorizationMonitor), the cost model in section 5, and
the dashboard. Sections marked *(spike)* must be validated before we commit to them.

**Two corrections Phase 2 made to what is written below, both from building it.**

*Section 4.1 overstates what the structural rule can do.* "Does executing this effect
require authority that only untrusted content supplied?" is not decidable from labels. A
legitimate reply to correspondence the user asked about, and an exfiltration to an address
found in an injected page, produce identical label traces. The implemented rule is narrowed
to out-of-scope effects reaching a *public* destination; everything else escalates. That
narrowing is finding F-07 and it is the concrete reason mechanism 2 exists.

*Section 5's ASK band is not the only thing that decides whether a human is asked.* A
refused ASK is remembered for the episode (D-024), because per-action granularity otherwise
lets one repetitive task spend the whole interruption budget on a question already
answered.

**Revised emphasis, 2026-08-29 (D-018).** E-00b showed that agents in our setting respect
explicit authorization boundaries almost perfectly (0/54) and infer permission under
under-specification (38.9%). The architecture does not change, but what carries the weight
does: the value is concentrated in the **ambiguous band**, so the AuthorizationMonitor's
calibration (section 4.3), the cost model that sets the ASK boundary (section 5), and the
ASK budget are load-bearing rather than refinements. A layer that only enforced explicit
boundaries would have almost nothing to enforce.

---

## 1. Layered view

```
                       +---------------------------------------------+
                       |                  Dashboard                   |
                       |     (replays AuditEvents; no logic of its own)|
                       +----------------------+----------------------+
                                              | reads
                       +----------------------v----------------------+
                       |              AuditLog (hash-chained)         |
                       +----------------------^----------------------+
                                              | writes
  user utterance                              |
        |                                     |
        v                                     |
 +---------------+     IntentScope     +------+------------------------------+
 | IntentCompiler|-------------------->|          AGENT FIREWALL             |
 +---------------+                     |  (reference monitor / policy point) |
        ^                              |                                     |
        | scope expansion              |  +-------------------------------+  |
        |                              |  | IntegrityMonitor              |  |
 +------+--------+   ASK / answer      |  | FlowMonitor                   |  |
 |   Human       |<------------------->|  | AuthorizationMonitor          |  |
 +---------------+                     |  +---------------+---------------+  |
                                       |                  |                  |
                                       |          PolicyCombinator           |
                                       +---------+---------------+-----------+
                                                 | ALLOW         | BLOCK/ASK-denied
        +---------------+   proposed             v               |
        |  Agent loop   |----------------->  ToolRouter          |
        | (LLM + tools) |<-----------------  (holds creds)       |
        +---------------+   result / refusal     |               |
                ^                                v               |
                |                        +---------------+       |
                +------------------------|  Sandbox world|<------+
                    labeled observations  +---------------+
```

Two structural rules make this a security architecture rather than a middleware stack:

1. **The agent has no credentials.** `ToolRouter` is the only holder. The agent emits
   *proposals*; effects happen only past the monitor.
2. **Labels are assigned at ingestion by the runtime**, at the point where data enters the
   trace. They are never parsed out of content, so they cannot be forged (threat A4).

## 2. Repository layout (planned)

```
agentfw/
  core/
    types.py           # IntentScope, ProposedAction, Effect, Label, Verdict, AuditEvent
    labels.py          # integrity + confidentiality lattices, join/meet, propagation
    effects.py         # effect ontology + tool -> effect mapping
    scope.py           # IntentScope algebra: narrow(), expand_via_consent(), satisfies()
    audit.py           # append-only hash-chained log, replay
  intent/
    compiler.py        # utterance -> IntentScope
    constraints.py     # budget/recipient/domain/time constraint extraction + checking
  monitors/
    integrity.py       # provenance propagation + dependency screener
    flow.py            # confidentiality lattice, declassification
    authorization.py   # the ML core: P(licensed | scope, effect, context)
    base.py            # Monitor protocol, Signal dataclass
  policy/
    combinator.py      # signals -> ALLOW/ASK/BLOCK via the cost model
    cost_model.py      # explicit costs; derives the ASK band
    ask.py             # consent-integrity rendering
  agent/
    loop.py            # ~300-line ReAct-ish loop, no framework
    providers/         # anthropic.py, openai.py, local_vllm.py behind one protocol
  sandbox/
    world.py           # seedable, snapshottable state
    tools/             # files, email, calendar, web, payments, storage
    fixtures/          # benign + malicious page/email/document content
  eval/
    suites/            # af_inject/, af_auth/, agentdojo_adapter/
    runner.py          # episode execution, retries, variance
    metrics.py         # ASR, BTC, FPR, ASK-rate, oversight efficiency, ECE, cost
    attacks/           # T1/T2/T3 generators
  ml/
    embed.py  cross_encoder.py  judge.py  cascade.py  distill.py
dashboard/             # Vite + TS, reads exported AuditEvent JSON
docs/                  # this directory
experiments/           # configs (yaml) + results (json/parquet) + notebooks
tests/
```

## 3. The core data model

### 3.1 Effects — the key abstraction

The brief risk-ranked *tools*. That is fragile: two tools can produce the same
consequence, and one tool can produce different consequences depending on arguments
(`http_request` GET vs POST). So we rank **effects**, and map (tool, arguments) → effect.

```python
Effect = (verb, resource_class, reversibility, externality, magnitude)

verb          ∈ {READ, WRITE, CREATE, DELETE, SEND, PUBLISH, PURCHASE, EXECUTE, GRANT}
resource_class∈ {PUBLIC_WEB, USER_FILES, SECRETS, EMAIL, CALENDAR, CONTACTS,
                 FINANCIAL, CLOUD_STORAGE, SYSTEM}
reversibility ∈ {REVERSIBLE, COSTLY_TO_REVERSE, IRREVERSIBLE}
externality   ∈ {NONE, VISIBLE_TO_THIRD_PARTY, BINDING_ON_USER}
magnitude     : optional scalar bound (dollars, recipient count, bytes, file count)
```

`EffectClass = (verb, resource_class)` is the unit that `IntentScope` authorizes.
The remaining fields modulate the cost model rather than membership.

**Why this matters:** it is what lets "find a flight" and "book a flight" differ. Both
involve the travel tools; only one licenses `(PURCHASE, FINANCIAL)`.

**Known weakness:** the ontology is finite and hand-built, so effect *mapping* accuracy is
itself a measurable component and a real limitation (THREAT_MODEL section 4.4). We will
report a confusion matrix for the mapper, not assume it is correct.

### 3.2 Labels

Two independent lattices, following FIDES.

```
integrity (higher = more trusted):
    SYSTEM > USER > AGENT_DERIVED > UNTRUSTED_TOOL > UNTRUSTED_{WEB,EMAIL,DOC}

confidentiality (higher = more restricted):
    SECRET > PRIVATE > PUBLIC
```

Propagation: any value derived from multiple sources takes the **meet** of integrity
(least trusted wins) and the **join** of confidentiality (most restricted wins). Tool
arguments inherit from the trace spans they were derived from.

### 3.3 IntentScope

```python
class IntentScope:
    objective: str
    authorized_effects: set[EffectClass]  # deny-by-default
    constraints: list[Constraint]  # budget, recipient, domain, time, glob
    declassifications: list[Declassification]  # what SECRET/PRIVATE data may leave, to where
    grants: list[Grant]  # each with provenance -> a USER turn id
    open_questions: list[str]
```

Operations:
- `narrow(...)` — allowed from any source, including untrusted observations.
- `expand_via_consent(answer)` — allowed **only** from a USER-labeled ASK answer. Any other
  caller raises. This is P1 from the threat model, enforced by construction.
- `satisfies(effect) -> (bool, reason)` — membership + constraint check.

## 4. The three monitors

Each implements `Monitor.evaluate(action, trace, scope) -> Signal`, where a `Signal`
carries a verdict contribution, a confidence, and human-readable evidence.

### 4.1 IntegrityMonitor

Two mechanisms, deliberately layered:

1. **Structural (in TCB, deterministic).** Does executing this effect require authority
   that only untrusted content supplied? If the effect class is not in scope and the only
   support for it in the trace is untrusted, that is a structural violation → BLOCK. This
   alone handles the canonical `.env` example, and it does so without any model.
2. **Dependency screening (outside TCB, ML).** For actions *within* scope, how much did
   untrusted spans influence the argument values? Two candidate implementations, following
   RTBAS:
   - **LM-as-judge screener** — works with API models. Default.
   - **Attention-saliency screener** *(spike)* — needs open-weight models with attention
     access; higher fidelity, much narrower applicability. **RISK R-03.**

   We will implement (a), evaluate (b) on a local model only if the spike succeeds, and
   report the comparison. If (b) is infeasible we say so and drop it — the structural rule
   carries most of the weight anyway, which is itself a finding.

### 4.2 FlowMonitor

Mostly deterministic and mostly boring, which is the point.

- Compute the confidentiality join of the action's arguments.
- Compute the destination trust of the effect (who can observe the result).
- Rule: `confidentiality(args) > permitted_by(destination)` → requires a declassification
  grant in scope. Absent → BLOCK if the destination is untrusted/attacker-controlled,
  ASK if the destination is plausible but ungranted.
- A small sensitive-pattern detector (keys, tokens, PII shapes) upgrades labels at
  ingestion for content that arrives without a clear source classification.

Conceded: covert/steganographic channels (THREAT_MODEL 4.5).

### 4.3 AuthorizationMonitor — the ML core

Estimates `P(the user licensed this effect | IntentScope, Effect, trajectory context)`,
**calibrated**, because the combinator needs a probability rather than a score.

Post-E-00b this component's job is specific: the interesting inputs are not actions that
contradict the instruction (rare, and caught structurally) but actions the instruction
**left open**. Calibration therefore matters more than accuracy at the extremes — the whole
question is where the uncertain middle sits and how wide it is.

Candidate approaches, to be compared (this is EXPERIMENT E-02, the intellectual centre of
the project):

| # | Approach | Cost | Hypothesis |
|---|---|---|---|
| M0 | Effect-class membership only (no ML) | ~0 | Surprisingly strong. Must be beaten to justify the ML. |
| M1 | Bi-encoder cosine(objective, action description) | very low | **Will fail on overreach.** Predicted AUC near chance on AF-Auth, good on AF-Inject. |
| M2 | Cross-encoder over (objective, effect description) | low | Better than M1; still confuses relevance with authorization. |
| M3 | Small guard model (PromptGuard-2, Qwen3Guard-0.6B) | low | Good on injection, blind to overreach (wrong training objective). |
| M4 | LLM judge with a structured authorization rubric | high | Strong but expensive and variance-prone. |
| M5 | **Cascade**: M0 gate → M2 → M4 only in the uncertain band | medium | Best cost/accuracy point. The engineering contribution. |
| M6 | **Distilled encoder** trained on M4's labels over generated scope/action pairs | low after training | The honest "we trained a model" contribution — *only if* M5 shows M4 is the bottleneck. |

M6 is conditional on purpose (see DECISIONS D-011): we do not train a model to be able to
say we trained a model.

Calibration is a first-class metric here (ECE, reliability diagram), because the entire
ASK/ALLOW boundary is derived from the probability.

## 5. PolicyCombinator and the cost model

The brief proposed combining signals into a risk number. We are not doing that — a
hand-tuned weighted sum is unfalsifiable and is exactly what makes these projects look
like hackathon work.

Instead, decisions come from an explicit cost model:

```
C_block_benign      cost of blocking a legitimate action  (utility loss)
C_allow_harmful     cost of allowing an unlicensed action (varies by effect: reversibility,
                                                           externality, magnitude)
C_ask               cost of one human interruption        (the attention budget)
```

Given calibrated `p = P(licensed)`, expected costs are:

```
E[ALLOW] = (1 - p) * C_allow_harmful(effect)
E[BLOCK] = p * C_block_benign
E[ASK]   = C_ask + (1 - p) * epsilon_reviewer_error * C_allow_harmful(effect)
```

Choose the minimum. This yields an **ASK band** in `p` whose width scales with
`C_allow_harmful / C_ask` — i.e. the system automatically asks more about irreversible,
externally-visible, high-magnitude effects and less about reversible ones. Sweeping
`C_ask` sweeps the interruption budget and **generates the trade-off curve that is our
headline figure**.

Hard structural gates (threat-model P1–P4) run *before* this and can only force BLOCK; the
cost model never overrides them. That separation is what keeps the ML outside the TCB.

**ASK budget.** Each episode has a budget `B`. On exhaustion the firewall fails **closed**
(BLOCK), which is the correct response to an ASK-flooding attack (A6) and is what
arXiv:2606.08919's inverted-U result implies.

## 6. Agent loop and providers

A plain tool-calling loop we own end to end. No LangChain / LlamaIndex / AutoGen.
Rationale in D-002: the object of study is precisely the tool-call boundary and the trace,
and frameworks abstract exactly that away while adding version churn and hidden prompts.

`LLMClient` protocol: `complete(messages, tools) -> (text, tool_calls, usage)`.
Implementations: Anthropic, OpenAI, and a local OpenAI-compatible endpoint (vLLM/Ollama)
so we can run open-weight models for the white-box attack tier and the saliency spike.

The loop records a **trace** of labeled spans; this is what the monitors read and what the
audit log serializes.

## 7. Sandbox

Deterministic, seedable, snapshot/restore per episode, entirely in-process (SQLite +
in-memory). No real network reachable from tools; "web pages" are local fixtures served
through the same interface a real fetch would use.

Tool families: filesystem, email, calendar, web fetch/search, payments stub, cloud storage,
contacts. Chosen to cover every `(verb, resource_class)` pair we care about with the
smallest possible tool count.

LivePI shows a VM-backed world is achievable and more realistic; we deliberately choose the
in-process world for determinism and reproducibility, and note the fidelity gap as a stated
limitation.

## 8. Audit and dashboard

`AuditEvent` per proposed action: action, effect, all monitor signals with evidence spans,
scope snapshot, cost-model inputs, verdict, latency, tokens. Hash-chained so tampering is
detectable, and complete enough to **replay the decision offline without re-running the
LLM** — which is what makes the dashboard honest rather than a scripted animation.

The dashboard renders the trajectory tree from exported events. It contains no decision
logic. If a decision is not in the log, it does not appear on screen.

## 9. What is deliberately simple

- No message queue, no microservices, no distributed anything.
- No plugin system until there is a second consumer of the interface.
- Config is YAML + pydantic-settings; experiments are YAML files under `experiments/`.
- The dashboard is a static build over exported JSON, not a live service.
