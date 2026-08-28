# PROJECT STATE

**Read this first.** It is the handoff document between development sessions.

**Last updated:** 2026-08-28 (end of Phase 0)
**Current phase:** Phase 0 complete. Phase 1 not started, awaiting user review.

---

## 1. Where we are

Phase 0 (research, specification, architecture) is **complete**. No code exists yet — that
is intentional; the brief specified Phase 0 as design-only.

Delivered:

| Document | Purpose |
|---|---|
| `docs/RELATED_WORK.md` | Landscape survey; the honest novelty argument |
| `docs/PROJECT_SPEC.md` | Authoritative project description (supersedes the brief) |
| `docs/THREAT_MODEL.md` | Principals, attacker capabilities, failure classes, conceded threats, claimed properties |
| `docs/ARCHITECTURE.md` | Proposed design, data model, monitors, cost model, repo layout |
| `docs/EVALUATION.md` | Suites, metrics, baselines, hygiene, falsification criteria |
| `docs/DECISIONS.md` | D-001…D-014 with reasoning |
| `docs/ROADMAP.md` | Refined phases 1–7 |
| `docs/EXPERIMENTS.md` | E-00…E-09 defined in advance, with registered predictions |
| `CLAUDE.md` | Working agreement for future sessions |

## 2. The thesis in one paragraph

Agent safety failures split into **hijacking** (untrusted content redirects the agent) and
**overreach** (an un-hijacked agent takes a consequence the user never licensed). Public
benchmarks have largely saturated the first and barely instrument the second. Agent
Firewall is a runtime reference monitor that maintains an intent-derived, deny-by-default
**authorization scope over effect classes**, enforces four structural properties without
any ML in the trusted path, and uses a calibrated authorization model plus an explicit cost
model to spend a **finite human-attention budget** efficiently. Headline metric: **oversight
efficiency** — harm averted per interruption.

## 3. Biggest changes from the original brief

1. Injection defense demoted from headline to component (D-001).
2. Risk attaches to **effects**, not tools (D-003).
3. No single combined risk score; an explicit expected-cost model instead (D-005).
4. ML is deliberately outside the trusted computing base (D-006).
5. Goal–action semantic similarity demoted to a weak signal, with a **pre-registered
   prediction that it fails on overreach** (D-012, E-01).
6. Human interruption promoted to a first-class evaluated axis.
7. Phase 1 now ends with a go/no-go experiment rather than a demo.

## 4. What happens next — Phase 1

**Do not start without user confirmation.** See `docs/ROADMAP.md` Phase 1.

Ordered task list for the next session:

1. `pyproject.toml` (uv), Python 3.12, pydantic v2, pytest, ruff. Package skeleton
   `agentfw/` per `ARCHITECTURE.md` section 2.
2. `agentfw/sandbox/world.py` — seedable, snapshottable state; SQLite + in-memory.
3. Tool families: files, email, calendar, web (local fixtures), payments stub, storage,
   contacts. Each tool declares the `Effect` it produces as a function of its arguments —
   even though the effect ontology is not enforced until Phase 2.
4. `agentfw/agent/loop.py` + `providers/` (Anthropic, OpenAI, local OpenAI-compatible).
   **Trace spans must carry ingestion-time labels from the first commit.**
5. Scenario format (YAML) + oracle interface. Build the *format and generator* now — Phase 5
   is scaling, not inventing (see ROADMAP sequencing risks).
6. Dev slices: 15–20 benign tasks, 8–10 AF-Auth minimal pairs, 5–8 AF-Inject scenarios.
7. **Run E-00.** Report OR / ASR / BTC with bootstrap CIs, n>=3 seeds, >=2 models.
8. Update `EXPERIMENTS.md` with results, `PROJECT_STATE.md` with status, then stop.

**Go/no-go:** if undefended overreach on the AF-Auth dev slice is under ~5%, stop and
re-frame before building any defense.

## 5. Open questions for the user

Listed in priority order; none block starting Phase 1 except Q1's default.

- **Q1 — Model budget.** Which providers/keys are available, and roughly what spend is
  acceptable? E-05 with n=3 seeds x 2 models x 8 defenses x ~300 scenarios is the dominant
  cost. Default assumption if unanswered: one frontier API model + one locally-hosted
  open-weight model, with aggressive caching and a small dev slice.
- **Q2 — Compute.** `nvidia-smi` is not on PATH on this machine, so we assume no local GPU.
  Is the university GPU reachable (SSH? Slurm? interactive?), and is it needed before
  Phase 3? Nothing before Phase 3 requires a GPU.
- **Q3 — Domain choice for AF-Auth.** Proposed: email, calendar, files, travel/purchasing,
  cloud storage. Any domain you would specifically like represented (e.g. a coding-agent
  domain, which is where the memorable real-world incidents happened)?
- **Q4 — Publication intent.** Is a workshop paper / arXiv preprint a goal? If yes, the
  dev/held-out discipline and adaptive-attack tiers become mandatory rather than
  recommended, and it changes how much Phase 5 we do.

## 6. Known risks (tracked)

| ID | Risk | Severity | Mitigation | Status |
|---|---|---|---|---|
| R-01 | Undefended agents may not overreach often enough to measure | **critical** | E-00 runs first, in Phase 1; go/no-go gate | open |
| R-02 | "Was this authorized?" ground truth is unreliable (prior work: Fleiss kappa 0.52) | high | minimal-pair construction (D-010) makes truth structural | mitigated by design |
| R-03 | Attention-saliency screening needs open-weight attention access; may be infeasible | medium | LM-judge screener is the default; saliency is a time-boxed spike | open |
| R-04 | Latency/cost blow-up from per-call LLM judging | medium | cascade (E-03); measured in E-08 | open |
| R-05 | A trivial input/output firewall already matches us on injection | **high** | do not compete there; B-04 is an explicit baseline and the contrast is the argument (D-001) | mitigated by framing |
| R-06 | Effect-ontology error dominates the error budget | medium | E-09 measures the mapper directly | open |
| R-07 | Scenario authoring is slow; Phase 5 overruns | high | build format + generator in Phase 1 | open |
| R-08 | Scope creep into multi-agent / memory / computer-use | medium | explicit out-of-scope list in PROJECT_SPEC section 7 | open |

## 7. Environment notes

- Python 3.12.9, git 2.55, node 24.15 on Windows 11. No NVIDIA GPU detected on PATH.
- Git repository initialized; no commits yet at time of writing.
- No dependencies installed, no virtualenv created yet.
