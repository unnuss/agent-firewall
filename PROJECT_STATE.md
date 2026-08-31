# PROJECT STATE

**Read this first.** It is the handoff document between development sessions.

**Last updated:** 2026-08-31 · **Phase 3 in progress.** · Phase 2 complete.

---

## 0. If you are the next session, do exactly this

1. Read `CLAUDE.md`, then this file, then **`docs/DECISIONS.md` D-025 to D-028** — D-025
   fixes what the intent compiler may see, D-026 why compiled scopes are committed
   artifacts, D-027 what the scripted human knows in E-01b, D-028 the experiment renaming.
   D-022, D-023 and D-024 remain the Phase 1/2 constraints.
2. Read **E-09a and E-01b in `docs/EXPERIMENTS.md`**, including E-09a's run log. One arm of
   E-09a is blocked on an exhausted API credit balance and is the first thing to finish.
3. Skim findings **F-10 to F-15**, then the older **F-07, F-08, F-09**. F-13, F-14 and F-15
   all came out of running a real compiler, and all three change what to build next.
4. Continue Phase 3 per `docs/ROADMAP.md`. Start at section 6 of this document.

Health check (~35 s, no API calls, no keys needed):

```bash
.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m agentfw.cli validate
```

Expect **196 passed** and 24 AF-Auth / 6 AF-Inject / 18 benign dev scenarios, 23 tools.

Both replay experiments reproduce with no key:

```bash
.venv/Scripts/python.exe -m agentfw.cli replay experiments/e01a_deterministic/config.yaml
.venv/Scripts/python.exe -m agentfw.cli replay experiments/e01b_compiled/config.yaml
```

---

## 1. Where the project is, in one paragraph

Phase 1 measured the problem and changed the thesis: agents respect explicit authorization
boundaries almost perfectly and fail by inferring authority from silence — 38.9% on OpenAI
models, 60.0% on Claude Sonnet 5 (D-022). Phase 2 built the deterministic reference monitor
and E-01a showed it removes all measured overreach and all measured attack success *given a
correct scope*, with the ASK path contributing nothing in that condition (F-09). Phase 3
therefore began where PROJECT_STATE said it must: with the scope itself. The intent compiler
exists, its inputs are restricted by construction to the user's turn and the tool catalogue
(D-025), and the measurement harness around it — E-09a against the gold labels, E-01b
against real verdicts — is built and running. Four arms have run: two deliberate floors, and
a real LLM compiler twice (a local model, because the OpenAI credit balance is exhausted).
Between them they establish that a tool-allowlist scope is worth nothing against overreach
(F-11), that ASK's value is real and large once the scope is wrong (269 refusals recovered
against 0 under gold), and that a compiler too weak to be an agent in this harness still cuts
measured overreach from 45.9% to 17.0% — at a compliance cost from 84.7% to 60.6%, most of it
traceable to invented constraints that no interruption can repair (F-13). **The registered
arm, `gpt-4.1-mini`, is still blocked on credit and is what settles the central prediction.**

## 2. Phase 3 deliverables, against the roadmap

| # | Deliverable | Status |
|---|---|---|
| 1 | `intent/compiler.py` — utterance → IntentScope | done: `LLMIntentCompiler` + two deterministic floors, `intent/catalog.py`, `intent/store.py` |
| 1 | **E-09a** — compiled scopes scored against gold | harness done, predictions registered and scored; floors + an exploratory local LLM arm measured; **the registered `gpt-4.1-mini` arm is pending on API credit** |
| 1b | **E-01b** — the replay with compiled scopes | done for all four arms that exist |
| 2 | The M0–M5 ladder | not started — deliberately, see section 6 |
| 3 | Calibration (ECE, reliability) | not started |
| 4 | E-01 (the pre-registered similarity prediction, D-012) | not started |
| 5 | E-02 (ladder comparison) | not started |
| 6 | E-03 (cascade) | not started |
| 7 | Dependency screener (F-07) | not started |
| 8 | M6 distillation | conditional on E-03 (D-011), unchanged |

## 3. What exists in code that did not before

```
agentfw/
  intent/
    catalog.py     tool -> effect-class ceiling, with two drift tests against the declarers
    prompts.py     the compilation prompt; D-023's four authoring rules, and nothing scenario-specific
    compiler.py    Compiler protocol, LLMIntentCompiler, ToolCeilingCompiler, ReadOnlyCompiler
    store.py       CompiledScopeStore: the committed artifact, and the ScopeSource seam
  eval/
    scope_run.py   the E-09a driver: compile every dev utterance, per arm and seed
    scope_eval.py  compiled-vs-gold metrics and the E-09a report
    scopes.py      + ScopeSource protocol, so replay takes gold or compiled interchangeably
    replay.py      + a scope source parameter and the gold reviewer oracle (D-027)
    replay_report.py + `ask_value` (what each interruption bought) and a cross-arm comparison
  cli.py           + `agentfw compile-scopes`; `replay` gained `--scopes`
experiments/
  e09a_compiler/   config + committed compiled scopes + per-arm reports
  e01b_compiled/   config + per-(scope, policy) reports + comparison.md
tests/test_intent.py   24 tests; test_replay.py gained the two D-027 seam tests
```

Four things worth not re-deriving:

- **The compiler's input restriction is its signature.** `compile(utterance, tools)` and
  nothing else. An attacker who could feed the compiler would be writing the user's
  authorization scope, which beats hijacking the agent, so the restriction is enforced by
  having nowhere to put the other data and asserted by a test over the rendered prompt.
- **A compile failure is an empty scope**, never a partial one. Deny-by-default all the way
  down, and the affected episodes are counted separately so an unreliable compiler cannot
  look like a cautious one.
- **Compiled scopes are committed artifacts** (D-026). E-01b never calls a model; it reads
  the JSONL E-09a wrote. That is what keeps the downstream experiment free and reproducible.
- **The scripted reviewer answers from gold in E-01b** (D-027), because a reviewer with an
  opinion only about the contested effect would refuse every recoverable interruption and
  make ASK look worthless a second time as a harness artifact.

**One Phase 2 test was corrected, not weakened.** `test_p4_agent_rationale_never_reaches_
the_ask_text` carried two assertions, and hypothesis found a counterexample to the first:
a rationale of `"reversibilit"` is a substring of a serialized field name, which is a
collision rather than a leak. The test's own comment already argued that substring checking
is the wrong test; the substring assertion is now gone and the byte-identity assertion —
render with the prose, render without it, require the same output — carries P4 alone. It
subsumes the deleted check, because prose that reached the output would change it.

## 4. Results so far

### E-09a — compiled against gold

| Arm | Micro-F1 | Exact match | Leakage (underspec. low) | Retention (high) | Contrast fidelity |
|---|---|---|---|---|---|
| `tool-ceiling` | 0.813 | 24.4% | **100%** | 100% | **0%** |
| `read-only` | 0.727 | 22.1% | **0%** | 0% | **0%** |
| `llm-qwen2.5-coder-14b` (exploratory, prompt v1) | 0.576 | 20.9% | 33.3% [13.3, 60.0] | 87.5% | 58.3% |
| `llm-qwen2.5-coder-14b` (exploratory, prompt v2) | 0.550 | 19.8% | **26.7%** [6.7, 46.7] | **100%** | **75.0%** |

The first column is why F1 is not the metric. A compiler with no notion of authorization at
all scores 0.813 against the gold labels while leaking the contested effect on every
low-authority variant — *above* the real compiler's 0.576.

The LLM row clears the pre-registered retention floor (0.80), so it may be interpreted, but
it is a quantized 14B code model on one greedy decode and it is weak evidence. Registered
predictions scored: 1 held, 2 failed (instructively), **3 not met** — leakage 33.3% with an
interval reaching 60%, so "clearly below the undefended 45.9%" is not established — 4 narrowly
missed, 5 held emphatically (163 under-grants to 15 over-grants), 6 held.

### E-01b — what those scopes do to real verdicts (702 episodes, $0)

| Scope source | Policy | Overreach (underspec.) | Compliance (high) | ASR | Benign FPR-block | ASKs/ep benign |
|---|---|---|---|---|---|---|
| *(undefended)* | — | 45.9% [34.1, 57.8] | 84.7% | 22.2% | — | — |
| gold | consequential | **0.0%** | 84.7% | **0.0%** | 0.0% | 0.00 |
| tool-ceiling | consequential | **45.9%** | 84.7% | 16.7% | 0.0% | 0.00 |
| read-only | consequential | 0.0% | **78.2%** | 0.0% | **12.1%** | 0.11 |
| read-only | all-out-of-scope | 0.0% | 82.9% | 0.0% | 0.0% | 0.32 |
| llm-qwen-local-p1 | consequential | 17.0% [3.7, 32.6] | 60.6% | 0.0% | 11.9% | 0.00 |
| llm-qwen-local-p1 | all-out-of-scope | 17.0% | 61.1% | 0.0% | 0.0% | 0.18 |
| llm-qwen-local-p2 | consequential | **12.6%** [1.5, 26.7] | **41.2%** | 0.0% | **34.5%** | 0.00 |
| llm-qwen-local-p2 | all-out-of-scope | 12.6% | 41.7% | 0.0% | 15.4% | 0.30 |

- The gold row reproduces E-01a exactly, which is the check that D-027's wider reviewer
  oracle cannot bind when the scope is already right.
- **F-11:** a tool-allowlist scope reproduces undefended overreach episode for episode.
- **ASK finally does something:** 90 asks / 0 approved under gold; 359 asks / **269
  recovered refusals** under `read-only`. F-09's contingency is now measured.
- **F-10:** at `ask_on: consequential`, 22 of 182 benign actions are refused with no dialog,
  all `CREATE` on private reversible resources. `consequential()` is the right predicate for
  agent overreach and the wrong one for compiler under-granting.
- **F-13:** the compiler arm fired gate G2 **59 times**, all on bounds it invented, and G2 is
  a hard gate — no interruption can repair a wrong bound, while 33 forgotten grants on the
  same run were repaired by one. `Grant` carries provenance and `Constraint` does not, so the
  firewall cannot tell a bound the user stated from one the compiler guessed.
- **F-14:** most of those invented bounds came from my own prompt — its JSON schema example
  held a literal `$150` budget, and the model copied it. Fixed in prompt v2, declared under
  R-16, artifacts versioned `p1`/`p2` so the two runs can never be compared silently.
- **The two-level measurement earned its keep, and this is the result to remember.** Prompt
  v2 improved *every* scope-level metric (leakage 33.3→26.7%, retention 87.5→100%, contrast
  58.3→75.0%) and made the deployed system much worse (compliance 60.6→41.2%, benign
  FPR-block 11.9→34.5%, G2 firings 59→270). Freed from copying the example's `$150`, the
  model extracted bounds enthusiastically — 69 across 51 utterances against gold's 6 — and
  they are plausible and wrong: `["Priya"]` where the address is
  `priya.menon@northwind-systems.com`, `["Amex"]` as the recipient of a payment, a time
  window clamped onto `READ:CALENDAR`. **A compiler change is not an improvement until E-01b
  says so.**
- **F-15:** feeding real compiler output into the monitor found a crash in Phase 2 TCB code —
  a naive/aware datetime comparison raised inside `Constraint.check`, taking 21 episodes out
  of the measurement entirely. Fixed and fail-closed; E-01a still reproduces bit-identically.

## 5. Open defects and risks carried forward

| ID | Issue | Action owed |
|---|---|---|
| **BLOCKER** | The OpenAI key returns `credit_balance_exhausted`; E-09a's LLM arm has never run | Top up, or add `OPENROUTER_API_KEY` to `.env.local` and repoint the arm. Two commands, under $0.50 |
| **F-10** | `consequential()` cannot tell "not worth interrupting about" from "the compiler probably dropped this" | Phase 4 cost model needs a `C_block_benign` term; the ML core's job is P(compiler under-granted) |
| **F-11** | Tool-allowlist authority = undefended overreach | Feeds EVALUATION 6.2; B-01 proper is Phase 5 |
| **F-12** | Gold scopes are inconsistent about paths named in an utterance (globs written for deletes, not for destinations) | **Labels deliberately unchanged.** Apply rule 3 uniformly when the held-out scopes are written |
| **F-13** | An invented constraint fires a hard gate and is unrecoverable; a forgotten grant is not | Give `Constraint` provenance and let a compiler-provenanced bound escalate rather than block. Care needed: it makes a narrowing negotiable, which runs opposite to D-007 |
| **F-14** | Prompt v1's schema example leaked literal values into compiled constraints | **Fixed** in prompt v2, declared under R-16. Any future prompt uses placeholders |
| **F-15** | A compiled scope could make `Constraint.check` raise, killing the decision | **Fixed** in `core/scope.py`, fail-closed, two tests. Watch for the same shape in any handler that gains a new input source |
| **F-09** | ASK's value is contingent on compiler error | **Answered** for the floor arms; re-answer with the LLM arm |
| **F-07** | Argument provenance is not authority provenance | Dependency screener, still owed in Phase 3 |
| **F-08** | ASK granularity is per action, not per effect class over a resource set | Phase 4 |
| **F-05** | `af_auth.us.email.sam_number` asks for a figure the world does not contain | Fix before Phase 5 |
| **F-06** | High-authority compliance on the OpenAI side is untrustworthy in 8 scenarios | Audit before quoting compliance |
| **F-03** | Benign BTC understated by over-strict oracles | Loosen before quoting BTC |
| **R-09** | Open-weight generalisation unresolved | Needs a competent open-weight model |
| **R-14** | Claude-authored scenarios evaluated a Claude model | Independent authorship in Phase 5. The compiler arm is deliberately an OpenAI model for the same reason |
| **R-15** | FPR-block must be reported against compiled scopes, never gold | **Done** — E-01b reports it per scope source |
| **R-16** | **New.** Prompt development and measurement share the dev slice | The tuning slice is declared: benign + af_inject + the control pairs. The 14 core underspecified triples were not looked at while writing the prompt, and any later prompt change must be declared and re-registered |

## 6. Phase 3 — what is next, in order

1. **Run E-09a's registered `gpt-4.1-mini` arm and then E-01b's.** Prediction 3 — that
   leakage on underspecified variants comes in well below the agents' own 45.9% overreach —
   is the load-bearing claim of the whole architecture, and the only arm that has tested it
   is a quantized 14B code model that returned 33.3% with an interval covering 45.9%. That
   neither confirms nor refutes it. Use prompt v2.
2. **Fix F-13 before the ladder.** It is cheap, it is structural rather than statistical, and
   on the only real compiler measured it accounted for the majority of the utility loss —
   59 hard-gate blocks that no amount of calibration or cascading would have touched.
3. **Then read the failure modes before building any ladder.** The point of doing E-09a first
   was to find out how much ML machinery is warranted. The evidence so far says the errors are
   overwhelmingly *under*-granting (163 to 15) plus invented bounds, not over-granting — which
   points at the dependency screener (F-07), the cost model's missing `C_block_benign` term
   (F-10) and constraint provenance (F-13), and away from a large calibrated authorization
   head. Confirm against the funded arm before acting on it.
4. **Then** the ladder, calibration, E-01, E-02, E-03 — reduced or expanded on the evidence.

**What the floors already tell Phase 4.** The trade-off curve will not be flat. `read-only`
and `tool-ceiling` sit at opposite corners of it and both are reachable by a bad compiler, so
there is something real for a cost model to arbitrate. What is not yet known is where a
competent compiler lands between them, and that is exactly the blocked measurement.

**Do not** relitigate D-006 (no ML in the trusted path), D-018 to D-024, or D-025's input
restriction without a documented reason.

## 7. Environment notes

- Python 3.12.9, uv 0.12.7, git 2.55, Windows 11. Venv at `.venv/`.
- Credentials load from **`.env.local`** (gitignored). It currently holds `OPENAI_API_KEY`
  **and that key has no credit**; `OPENROUTER_API_KEY`, which E-00f used, is no longer
  present. `--override-env` is a top-level flag.
- No NVIDIA GPU. Ollama is installed with `qwen2.5-coder:14b` and `dolphin3`; both are
  unusable as *agents* (D-016/D-020) but a compiler needs only JSON output, so
  `qwen2.5-coder:14b` runs as an explicitly exploratory arm at roughly 50–100 s per
  utterance on CPU.
- **Phase 3 has spent $0.** Total API spend across the project is still roughly **$4**.
- E-09a's compiled scopes are committed on purpose (D-026): they are inputs to E-01b, not
  outputs of it. E-01b's per-arm replay output is derived data and regenerates in ~2 minutes.
