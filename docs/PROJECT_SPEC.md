# Agent Firewall — Project Specification

**Status:** authoritative as of Phase 0 (2026-08-28). Supersedes the original brief where
they conflict; see `DECISIONS.md` for the reasoning behind every deviation.

---

## 1. One-sentence description

Agent Firewall is a runtime authorization layer for tool-using LLM agents that maintains a
structured model of what the user actually licensed, checks every proposed tool call
against it, and spends a **finite human-attention budget** as efficiently as possible —
blocking what is clearly unlicensed, allowing what is clearly licensed, and **asking when
the user's instruction did not settle the question and the consequence is large enough to
be worth an interruption.**

## 2. The thesis, stated so it can be falsified

**Revised 2026-08-29 in light of E-00 and E-00b.** The original wording claimed that agents
commonly take consequences the user never licensed. Our own measurements do not support
that in general, and the revision below is what they do support. The superseded wording is
preserved in section 2.2 rather than deleted.

### 2.1 The thesis

> Agent safety failures split into two families requiring different machinery:
> **hijacking** (untrusted content redirects the agent) and **overreach** (an un-hijacked
> agent produces a consequence the user never licensed). The field has largely solved the
> first on public benchmarks and has barely instrumented the second.
>
> Within overreach, the failure is **not** that agents disregard explicit boundaries. In
> our tested setting they respect those almost perfectly. The failure is that
> **underspecified instructions cause agents to infer permission for consequential effects
> the user never clearly licensed** — the user states a goal without naming an action, and
> the agent supplies the higher-consequence action.
>
> A runtime layer that models *intent scope* explicitly can catch this at a
> human-interruption cost low enough to be usable. **Selective ASK — on consequential
> actions whose authorization the utterance left open — is therefore the central mechanism,
> not a fallback.** And semantic goal-relevance, the obvious first idea, is close to
> useless for it, because under-specification leaves relevance intact while destroying
> authorization.

### 2.2 What has actually been measured, and what the earlier wording got wrong

The original thesis read: *"A layer that models intent scope explicitly can catch overreach
at a human-interruption cost low enough to be usable."* It was silent on *which* overreach,
and implied breadth we have not demonstrated.

| Claim | Status |
|---|---|
| Agents overreach against explicit instructions | **Refuted in our setting.** 0/54 episodes across nine control scenarios (E-00b); 0/48 in E-00. |
| Agents overreach under under-specification | **Supported.** 38.9% [25.6, 52.2] of episodes, 13 of 15 scenarios, 7 domains (E-00b). |
| The difference is caused by ambiguity, not by consequence size | **Supported.** In 11 of 14 scenarios, changing only the wording of an equally-low-authority ask flipped the outcome, holding world, tools and contested effect fixed. |
| The finding holds across model families | **Not established.** Both models tested are OpenAI models. Replication (E-00c) is a precondition for Phase 2. |
| ASK is the right primitive for these cases | **Argued, not yet measured.** Under-specification is precisely the case where BLOCK is wrong (the user may well have meant it) and ALLOW is wrong (they may not). E-04 measures it. |

**Design consequence.** If explicit boundaries are already respected, a firewall that only
enforces explicit boundaries buys little. The value has to come from the ambiguous band —
which makes calibration, the cost model, and the ASK budget the load-bearing components
rather than the trimmings, and makes "how few interruptions can we spend" the right
headline question.

## 3. Why this framing and not the original one

The original brief centred on indirect prompt injection. Phase 0 research
(`RELATED_WORK.md`) established that IPI defense at the tool boundary is near-saturated on
all four standard public benchmarks by a *simple* input/output filter pair
(arXiv:2510.05244), and that at least six serious systems (CaMeL, FIDES, RTBAS, Progent,
LlamaFirewall, CommandSans) already occupy that space. Meanwhile a 2025 SoK
(arXiv:2512.06914) names "relevance is not authorization" as an open gap, a 2026 survey of
21 production agent systems (arXiv:2605.24309) finds that intent anchoring and trust
labeling have *zero production deployment* while approval fatigue is the dominant
complaint, and a 2026 paper (arXiv:2606.08919) shows the safety-vs-escalation curve is an
inverted U — escalating everything is *not* safety-optimal.

So: keep everything the brief asked for, **re-rank it**. Injection defense is a necessary
component and a reported result. Authorization-under-a-human-attention-budget is the
headline.

## 4. Non-negotiables (carried over from the brief, unchanged)

1. It is a runtime safety/trust layer for tool-using LLM agents.
2. It reasons about user intent, not bad words.
3. **Goal relevance and user authorization remain distinct concepts** — and we will
   measure the extent to which they are distinct.
4. Provenance/trust of environmental information is a major part of the design.
5. Consequence/risk matters and is context-dependent.
6. It protects real agent tool execution, not synthetic tool-call strings.
7. We evaluate security **and** useful task completion — plus, added in Phase 0, human
   interruption cost.
8. There is substantive AI/NLP/ML work.
9. Results are experimentally measured, with variance, and negative results are published.
10. The repository is portfolio/research-grade.

## 5. What the system does, precisely

### 5.0 What the layer is actually for

Given section 2, the layer's job is narrower and sharper than "stop agents doing bad
things". It is:

1. **Deny-by-default over effect classes**, so an effect the utterance never licensed
   cannot happen silently — this is what turns "the agent inferred permission" from an
   invisible event into a decision point.
2. **Route that decision point to a human when, and only when, the interruption is worth
   its cost** — the ambiguous band, weighted by irreversibility and externality.
3. **Keep hijacking out** structurally, so the ambiguity machinery is never the thing an
   attacker has to fool.

### 5.1 Position in the loop

```
user utterance
   |
   v
[ IntentCompiler ] --> IntentScope  (deny-by-default over effect classes)
   |
   v
agent loop  --(proposed tool call)-->  [ AGENT FIREWALL ]  --> ALLOW --> tool
                                              |                          |
                                              +--> BLOCK --> refusal ----+
                                              |               fed back
                                              +--> ASK ---> human ---> scope expansion
                                                                        (or denial)
```

The agent never holds tool credentials. The firewall is a reference monitor: it is the
only path to effect.

### 5.2 The three monitors

The brief listed ten questions. They are not ten independent checks — they collapse into
three concerns with genuinely different formalisms, and keeping them separate is what
makes our ablations meaningful.

| Monitor | Question | Formalism | ML content |
|---|---|---|---|
| **IntegrityMonitor** | Did untrusted content *cause* this action? | Integrity labels propagated over the trace + a dependency screener | Some (screener) |
| **FlowMonitor** | Is sensitive data crossing a trust boundary toward an unlicensed destination? | Confidentiality label lattice, deny-by-default declassification | Little (mostly deterministic) |
| **AuthorizationMonitor** | Did the user license *this consequence*? | Calibrated probability over an effect-class scope | **Most of it** |

A small, explicit **PolicyCombinator** turns their outputs into ALLOW / ASK / BLOCK using a
documented cost model — not a hand-tuned weighted sum.

### 5.3 The invariant that makes it a security system

> **Scope monotonicity.** The set of effects the agent is licensed to produce can only be
> *narrowed* by anything the agent or the environment does. It can be *widened* only by a
> human answering an ASK, and the widening is recorded with USER provenance.

Borrowed from Progent's narrowing/expansion split (arXiv:2504.11703), which uses an SMT
solver for the same purpose. This single rule is what stops "the webpage told me I was
pre-authorized" attacks structurally rather than statistically.

### 5.4 The property that protects the ASK channel

> **Consent integrity.** The text shown to a human in an ASK is rendered from
> firewall-derived structured facts (tool, normalized arguments, effect class, resource
> sensitivity, provenance of the triggering evidence). Agent-authored prose is never used
> as the approval prompt, and untrusted strings appearing in arguments are displayed
> quoted and labeled, never as narration.

Motivated by arXiv:2606.02668. Without this rule, an attacker who cannot get an ALLOW can
still get a human to click yes on a misleading dialog.

## 6. Core representations

These are the schemas everything else is built on. They will live in
`agentfw/core/types.py` as pydantic models.

- **`IntentScope`** — objective text; `authorized_effects: set[EffectClass]`;
  `constraints: list[Constraint]` (budget, recipient, domain, time window, resource glob);
  `open_questions`; provenance of each grant (which user turn licensed it).
  Deny-by-default: an effect class not present is not authorized.
- **`ProposedAction`** — tool name, normalized arguments, the agent's stated rationale,
  and the trace slice that produced it.
- **`Effect`** — `(verb, resource_class, reversibility, externality, magnitude)`. The
  *consequence*, decoupled from the tool that produces it. Two different tools that both
  send email produce the same effect class.
- **`Label`** — `integrity ∈ {SYSTEM, USER, AGENT_DERIVED, UNTRUSTED_WEB, UNTRUSTED_EMAIL,
  UNTRUSTED_DOC, UNTRUSTED_TOOL}`, `confidentiality ∈ {PUBLIC, PRIVATE, SECRET}`.
  Values in the trace carry labels; action arguments inherit the join of their sources.
- **`Verdict`** — `ALLOW | ASK | BLOCK`, plus every signal that contributed, plus a
  human-readable explanation generated from those signals.
- **`AuditEvent`** — append-only, hash-chained, one per proposed action; enough to replay
  the whole decision offline. The dashboard renders these and nothing else.

## 7. Scope

### In scope
- A deterministic, seedable sandbox world: files, email, calendar, web pages, a payments
  stub, a cloud-storage stub. Snapshot/restore per episode.
- One real tool-using agent loop (our own, ~300 lines, no agent framework) driving
  frontier and open-weight models through a provider abstraction.
- The three monitors, the combinator, the audit trail.
- Two evaluation suites: `AF-Inject` (hijacking) and `AF-Auth` (overreach, minimal pairs).
- An AgentDojo comparability run for external anchoring.
- Baselines: undefended, static allowlist, system-prompt warning, PromptGuard-2 classifier,
  per-call LLM judge, "confirm every write" (the production default), plus ablations.
- Adaptive attacks following the arXiv:2606.26479 protocol.
- A trace-replay dashboard driven by real audit logs.

### Out of scope (explicitly, for this project)
- Multi-agent / agent-to-agent trust delegation.
- Memory poisoning and cross-session persistence attacks.
- Real network access from the agent, real credentials, real money, real email.
- Computer-use / GUI agents.
- Model weights fine-tuning of the *agent* (we may distill a small *monitor*, see D-011).
- Formal verification / proofs of non-interference.
- A production-grade multi-tenant service, RBAC, or a control plane.
- Detection evasion research, offensive tooling beyond the fixed evaluation suites.

### Deliberately deferred (revisit only if Phase 5 leaves time)
- MCP proxy packaging.
- Attention-saliency dependency screening (needs open-weight models with attention access;
  see RISK R-03).
- A real human-subject study of approval fatigue.

## 8. Success criteria for the project

1. We can show, with numbers and error bars, that an undefended competent agent overreaches
   on a measurable fraction of benign tasks — establishing the problem exists.
2. Agent Firewall reduces overreach substantially at an interruption rate materially below
   "confirm every write", and we can draw the trade-off curve.
3. On injection, we are competitive with (not necessarily better than) the simple
   input/output firewall baseline, and we say so plainly.
4. At least one clean negative or surprising result is reported (current prediction:
   embedding similarity is near-useless for overreach).
5. Ablations show which components actually pay for themselves.
6. A reader can replay any decision in the dashboard and see exactly why it was made.
7. The repository reproduces every table with one command.
