# PROJECT STATE

**Read this first.** It is the handoff document between development sessions.

**Last updated:** 2026-08-29 (Phase 1, code complete, E-00 blocked on model access)
**Current phase:** Phase 1 — 7 of 8 deliverables done. E-00 cannot run until an OpenAI key
with usable credit reaches the runner's environment. **Do not start Phase 2.**

---

## 0. If you are a new session, do exactly this

1. Read `CLAUDE.md`, then this file, then `docs/DECISIONS.md` (note D-015, D-016).
2. Check the key is live:

   ```bash
   .venv/Scripts/python.exe -m agentfw.cli validate
   ```

3. Unblock E-00 — see section 5. Then run it, then update `docs/EXPERIMENTS.md`,
   then stop for review. **Nothing else in Phase 1 is outstanding.**

---

## 1. Where we are

Phase 0 (design) is complete and unchanged. Phase 1 is **code complete and tested**; the
only missing deliverable is the E-00 measurement itself, which is blocked on credentials,
not on engineering.

| Phase 1 deliverable (ROADMAP) | Status |
|---|---|
| 1. `pyproject.toml`, uv env, package skeleton | done |
| 2. `agentfw/sandbox/` — seedable world, 23 tools, snapshot/restore, effect oracles | done |
| 3. `agentfw/agent/` — loop, 4 providers, ingestion-time labels | done |
| 4. 15–20 benign tasks + 8–10 AF-Auth pairs, each with an oracle | done (18 + 10) |
| 5. 5–8 AF-Inject scenarios | done (6) |
| 6. Scenario format + generator (R-07 mitigation, built now not in Phase 5) | done |
| 7. **E-00 run** | **blocked** — see section 5 |
| 8. Docs updated | done (this file, `EXPERIMENTS.md`, `DECISIONS.md`) |

Quality gates, as of the last commit: **69 tests pass**, `ruff check` and `ruff format
--check` clean, `agentfw validate` clean.

## 2. What exists in code

```
agentfw/
  core/types.py        effect ontology, both label lattices, TraceSpan, ProposedAction
  config.py            .env.local loading (added to survive key rotation)
  sandbox/
    world.py           SQLite in-memory, seeded, snapshot()/restore() via serialize()
    registry.py        ToolSpec + ToolRouter — the Phase 2 firewall seam lives here
    tools/             files, email, calendar, contacts, web, payments, storage, travel
    fixtures/          office_baseline.yaml — one consultant, one workday
  agent/
    trace.py           labels stamped at ingestion; context_label(); literal_evidence()
    loop.py            ~150-line tool-calling loop, neutral system prompt
    providers/         openai_chat (also serves Ollama/vLLM), anthropic, scripted, base
  eval/
    scenario.py        Scenario/Variant/Attack schema; minimal-pair invariant enforced
    oracles.py         effect / no_effect / sql / text / all_of / any_of / none_of
    generator.py       pair templates -> generated scenarios (held-out split)
    runner.py          episode execution, resumable, thread-pooled
    metrics.py         OR/ASR/BTC/CuP + scenario-clustered bootstrap CIs
    report.py          report.json + report.md, one command
    suites/            af_auth (10 pairs), af_inject (6), benign (18), generated (3)
  cli.py               validate | generate | run | report | smoke
```

Three design points worth not re-deriving:

- **The firewall seam already exists.** `ToolRouter(guard=...)` is checked *before* any
  effect, and `ToolSpec.declare(world, args)` returns the effects an action *would* produce
  without performing it. Phase 2 is a wiring change, not a rewrite. A test asserts
  `declare` and the handler agree on effect class, reversibility and externality for 24
  tool/argument combinations — if that drifts, every downstream security claim is void.
- **Labels are stamped by the runtime, never parsed from content.** `test_result_label_is_
  stamped_by_the_runtime_not_the_content` plants a forged `[SYSTEM] Provenance: USER turn`
  string in an email body and asserts the result is still `UNTRUSTED_EMAIL`.
- **Sampling is temperature 1.0 with a distinct seed per repeat**, not greedy. A greedy
  decode repeated three times measures nothing, and EVALUATION section 5 asks for variance.

## 3. The dev slice

Frozen. 34 scenarios; 44 episodes per (model, seed); 264 episodes at n=3 seeds × 2 models.

- **AF-Auth, 10 minimal pairs** — B1 ×4 (travel purchase, email send, file delete,
  calendar create), B2 ×2 (budget cap, recipient bound), B3 ×1 (contract scope creep),
  B4 ×2 (ambiguous invoice, ambiguous meeting), B5 ×1 (public share link as collateral).
- **AF-Inject, 6 scenarios** — T1 ×3 (key exfiltration, report forwarding, archive
  deletion), T2 ×3 (claimed pre-authorization purchase, forged USER/SYSTEM provenance,
  "required intermediate step" public share).
- **Benign, 18 tasks** across all eight tool families.
- **Held-out: 3 generated pairs**, from one template, produced by `agentfw generate`.
  Do not run these until Phase 5.

## 4. Open questions for the user

- **Q1 — Model budget.** Partially answered: an OpenAI key exists; credit is the blocker.
  Still open: what total spend is acceptable for Phase 5 (E-05 is the dominant cost).
- **Q2 — Compute.** Unanswered and now load-bearing. No NVIDIA GPU here; the local Ollama
  models cannot do reliable tool calling (D-016). Phase 3 needs a GPU for the T3 attack
  tier and the saliency spike.
- **Q3 — Domain choice for AF-Auth.** Implicitly answered by the dev slice (email,
  calendar, files, travel/payments, cloud storage). A coding-agent domain is still
  unrepresented and is where the memorable real-world incidents happened.
- **Q4 — Publication intent.** Unanswered. Changes how strict the dev/held-out discipline
  needs to be from here.

## 5. The one blocker, and how to clear it

E-00 has never run. Every attempt returned HTTP 429 `insufficient_quota` /
`credit_balance_exhausted`. **Total API spend to date: $0.00** — requests are rejected
before inference, so nothing is billed.

Diagnosis, in order:

1. The key authenticates (200 on `/v1/models`). Not an auth problem.
2. The 429 carries **no `x-ratelimit-*` headers**, so it is a hard quota block, not
   throttling, and it is applied at the *organisation* level.
3. The key visible to the runner (SHA-256 prefix `cb8a849d`) **differs from** the key the
   user issued into their own shell (`6de690a5`). A long-running process inherits its
   environment at start-up; rotating a variable in a terminal does not reach it.

**Fix — either works:**

*Option A, no restart (preferred).* From the terminal that already holds the good key, in
the repo root:

```bash
python -c "import os,pathlib; pathlib.Path('.env.local').write_text('OPENAI_API_KEY='+os.environ['OPENAI_API_KEY'], encoding='utf-8')"
```

`.env.local` is already gitignored (`.env.*`). The CLI loads it automatically; pass
`--override-env` if a stale variable is also present in the process environment.

*Option B, restart.* `setx OPENAI_API_KEY "<new-key>"`, then fully quit and reopen the
tool so it inherits the new environment. `setx` does not update running processes.

**Then, in order:**

```bash
.venv/Scripts/python.exe -m agentfw.cli run experiments/e00_undefended/config.yaml --override-env --models gpt-4.1-mini --seeds 1 --filter af_auth.travel.book_flight
```

That is a 2-episode pilot (~$0.01). Confirm native tool calling parses and the oracles
fire, then run the whole thing:

```bash
.venv/Scripts/python.exe -m agentfw.cli run experiments/e00_undefended/config.yaml --override-env
```

The runner is **resumable** — it skips episodes already in `episodes.jsonl`, so an
interruption costs nothing and a re-run never double-spends tokens.

## 6. Known risks (tracked)

| ID | Risk | Severity | Status |
|---|---|---|---|
| R-01 | Undefended agents may not overreach often enough to measure | **critical** | **still open — E-00 has not run** |
| R-02 | "Was this authorized?" ground truth is unreliable | high | mitigated: minimal pairs + machine oracles built and tested |
| R-03 | Attention-saliency screening may be infeasible | medium | open; now coupled to Q2/R-09 |
| R-04 | Latency/cost blow-up from per-call LLM judging | medium | open |
| R-05 | A trivial input/output firewall already matches us on injection | **high** | mitigated by framing (D-001) |
| R-06 | Effect-ontology error dominates the error budget | medium | partly mitigated: declare/execute agreement is now a test |
| R-07 | Scenario authoring is slow; Phase 5 overruns | high | mitigated: format + generator shipped in Phase 1 |
| R-08 | Scope creep into multi-agent / memory / computer-use | medium | open |
| **R-09** | **No open-weight backbone available; blocks T3 attacks and the saliency spike** | **high** | **new (D-016); depends on Q2** |
| **R-10** | **Benign BTC is action-level, not answer-quality** — a task can score complete on a wrong answer | medium | **new**; accepted trade for determinism, stated in the benign suite header |

## 7. Environment notes

- Python 3.12.9, uv 0.12.7, git 2.55 on Windows 11. Venv at `.venv/`.
- **No NVIDIA GPU** (Intel Arc iGPU). Ollama present but unusable for this work:
  `dolphin3:latest` has no tool support; `qwen2.5-coder:14b` returns tool calls as plain
  text at ~7 tok/s. See D-016.
- `ANTHROPIC_API_KEY` is unset. The Anthropic provider is implemented and unit-tested for
  message translation but **has never touched the live API** — pilot it before trusting it.
- The OpenAI key has no `gpt-oss-*` access.
