# Threat Model

A defense with no stated threat model is not evaluable. This document says exactly what we
assume, what we defend against, what we concede, and how an attacker is allowed to behave
in our experiments.

---

## 1. Principals and trust

| Principal | Trust | Notes |
|---|---|---|
| **User** | Trusted, but *fallible and finite* | Not adversarial. May under-specify. Has a limited attention budget and degrades under load. |
| **Firewall (reference monitor)** | Trusted (TCB) | Deterministic core. Its ML components are *not* individually trusted; the invariants must hold even when a monitor is wrong. |
| **Agent LLM** | **Untrusted for control, useful for content** | We assume it can be fully hijacked. No defense may depend on the agent behaving well. |
| **Tools / sandbox world** | Semi-trusted | The tool *implementations* are trusted; the *data they return* is untrusted. |
| **Environment content** (web pages, emails, documents, tool outputs) | **Untrusted** | The primary attack channel. |
| **Attacker** | Controls all untrusted content | Cannot modify our code, the user's message, or the audit log. |

### Trusted computing base
The TCB is: the firewall's deterministic core (label propagation, scope monotonicity
check, effect ontology, policy combinator, audit chain), the sandbox tool implementations,
and the ASK rendering path. **Every ML component sits outside the TCB.** If the
authorization model is wrong, the worst outcome must be a wrong ASK/ALLOW on an action that
already passed the deterministic gates — never a silent scope expansion.

## 2. Attacker capabilities

The attacker **can**:
- Write arbitrary content into any untrusted surface the agent reads (web page, email body,
  document, tool response, file contents, calendar invite).
- Know the entire Agent Firewall design, prompts, thresholds and source code
  (Kerckhoffs — no security through obscurity).
- Craft **defense-aware** injections: claim pre-authorization, claim the firewall already
  approved, impersonate the user, impersonate the system, forge provenance markers.
- Chain attacks across steps (second-order: plant content now, exploit later in the same
  episode).
- Attempt to accomplish harm using **only tools the user already authorized**.
- Flood the ASK channel to exhaust the human reviewer's attention.

The attacker **cannot**:
- Modify the user's original utterance or any user response to an ASK.
- Modify firewall code, configuration, model weights, or the append-only audit log.
- Access the tool layer except through the firewall.
- Perform gradient-based white-box optimization against closed frontier models (we run
  GCG-style attacks only against open-weight models we host).

## 3. Failure classes we defend against

We separate two families because they need different machinery. This split is the
project's organizing idea.

### Family A — Hijacking (control-flow integrity)
The agent's behaviour is redirected by untrusted content.

- **A1 Indirect prompt injection.** Untrusted content introduces a new instruction.
  *Primary defense:* integrity labels + scope monotonicity. Untrusted content can never
  license an effect class.
- **A2 Goal hijacking / drift.** The agent abandons or extends the user's objective.
  *Primary defense:* effect-class scope; the objective text is only a secondary signal.
- **A3 Data exfiltration.** Sensitive data flows to an unauthorized destination.
  *Primary defense:* confidentiality lattice; declassification requires an explicit grant.
- **A4 Provenance spoofing.** Untrusted content forges "USER:" or "SYSTEM:" framing, or
  claims a prior approval.
  *Primary defense:* labels are assigned at ingestion by the runtime, never parsed from
  content. This is a structural, not statistical, defense.
- **A5 Consent-dialog manipulation.** The attacker cannot get ALLOW, so it engineers a
  misleading ASK that the human approves.
  *Primary defense:* consent integrity — ASK text is rendered from firewall-derived facts.
- **A6 ASK flooding.** The attacker deliberately triggers many escalations to exhaust
  reviewer attention (arXiv:2606.08919).
  *Primary defense:* per-episode ASK budget with a documented degradation policy
  (on budget exhaustion the firewall fails **closed**, not open).

### Family B — Overreach (authorization)
No attacker is involved. The agent, working correctly toward the stated goal, produces a
consequence the user never licensed.

- **B1 Consequence escalation.** "Find a flight" → purchase. "Draft an email" → send.
  "Show what could be deleted" → delete.
- **B2 Constraint violation.** Authorized action, violated bound: over budget, wrong
  recipient, wrong date, wrong account.
- **B3 Scope creep across steps.** Each step looks locally reasonable; the trajectory ends
  somewhere the user never licensed.
- **B4 Ambiguity resolved in the risky direction.** Under-specified request; the agent
  picks the higher-consequence reading without asking.
- **B5 Collateral effect.** The goal is achieved, plus an unlicensed side effect (files
  overwritten, a subscription created, a calendar shared).

Family B is what public benchmarks barely instrument, and it is where our contribution is.

## 4. Explicit non-goals / conceded threats

We state these so nobody reads a false claim into the results.

1. **A compromised or malicious user.** Out of scope by definition.
2. **A compromised firewall.** If the TCB is compromised, nothing holds.
3. **Model capability failures.** If the agent is simply too weak to do the task, the
   firewall does not fix that; it will show up as low utility for all defenses equally.
4. **Semantic laundering.** An attacker may express a harmful effect in terms whose effect
   class we mis-map. Our effect ontology is finite and hand-built; this is a real
   limitation and we will report the mapping accuracy explicitly.
5. **Steganographic / encoded exfiltration** inside otherwise-authorized payloads (e.g.
   secrets encoded into a legitimately-sent email body). Our FlowMonitor operates on
   labels and detectable sensitive patterns, not on arbitrary covert channels. Partially
   conceded; we will measure how far it gets.
6. **Attacks that require zero unauthorized effect.** If the attacker's goal is fully
   achievable within the user's authorized effect set and constraints, Agent Firewall by
   construction cannot stop it. This is the correct behaviour of a least-privilege system
   and the honest boundary of the approach.
7. **Human approval errors.** We model reviewer fatigue in evaluation but we do not run a
   human-subject study; approvals in experiments come from a scripted oracle with a
   configurable error model.
8. **Denial of service against the agent itself.** An attacker who only makes the agent
   fail (rather than do harm) succeeds against us. We count this as a utility loss, not a
   security failure, and report it.

## 5. Security properties we intend to claim

Stated as properties, so each can be tested by a targeted test case:

- **P1 (Structural).** No sequence of untrusted content can add an effect class to the
  IntentScope. *Test:* the entire A1/A4 suite plus a property-based fuzz over label
  propagation.
- **P2 (Structural).** Every executed action's effect class is a member of the IntentScope
  at execution time. *Test:* runtime assertion in the reference monitor; any violation is a
  crash, not a log line.
- **P3 (Structural).** Every SECRET-labeled value reaching an external-destination argument
  has an explicit declassification grant traceable to a USER turn.
- **P4 (Structural).** Every ASK rendering contains no agent-authored free text.
- **P5 (Statistical).** On AF-Auth, overreach rate is reduced by X at an interruption rate
  below "confirm every write". *Measured, with CIs.*
- **P6 (Statistical).** Benign task completion drops by no more than Y relative to
  undefended. *Measured, with CIs.*

P1–P4 are the ones worth being proud of, because they do not depend on a model being right.
When we write the README, the structural and statistical claims must be visually separated.

## 6. Attack generation protocol for experiments

Following arXiv:2606.26479, every defense we report is evaluated at three attack tiers:

- **T1 Naive.** Direct injected instruction, no defense awareness. (What most benchmarks
  contain.)
- **T2 Defense-aware.** The attacker knows the design: forged provenance, claimed
  pre-authorization, "necessary intermediate step" framing, effect-class laundering,
  ASK-flooding.
- **T3 Adaptive/optimized.** Automated search over injection strings against our open-weight
  configuration (GCG-style or PISmith-style), plus **the pre-authorized-tools-only attack**.

Headline numbers are reported at **T2**. Reporting only T1 would be dishonest;
T3 is expensive and runs on a subset.
