# PROJECT STATE

**Read this first.** It is the handoff document between development sessions.

**Last updated:** 2026-09-04 · **Phase 3.5 COMPLETE.** · **Next: Phase 4, with the ladder
question reopened (D-034).**

---

## 0. If you are the next session, do exactly this

1. Read `CLAUDE.md`, then this file, then **`docs/DECISIONS.md` D-034** — Phase 3.5's exit
   criterion was met in the negative and D-034 says exactly what that un-retires and what it
   does not. Then **D-033** (independently authored held-out labels), **D-032** (now marked
   reopened; read it for the argument, D-034 for its status), **D-031** (superseded but it is
   the reason Phase 3.5 existed), and **D-030** (constraint provenance). D-025 to D-029 cover
   the compiler's inputs, its artifacts, the reviewer oracle, experiment naming and
   credential precedence.
2. Read findings **F-16 → F-17 → F-18 → F-19** in `docs/EXPERIMENTS.md` **and then E-11**.
   The first four are Phase 3's argument in four steps on the dev slice; E-11 is what
   happened when it was pointed at unseen data. Reading F-16 alone gives the opposite
   conclusion to F-17; reading F-19 alone now overstates what replicates.
3. Read **F-29** before touching `monitors/flow.py` or quoting any compliance number.
4. **The Phase 3.5 apparatus boundary is real.** Every number from E-00, E-00b, E-00f,
   E-00h, E-01a and E-01b is **pre-repair**; every number from E-00g, E-00i and E-11 is
   **post-repair**. A `CONTRACT.md` sits in each pre-repair result directory. Never
   difference across it.

Health check (~55 s, no API calls, no keys needed):

```bash
.venv/Scripts/python.exe -m pytest -q && .venv/Scripts/python.exe -m agentfw.cli validate
```

Expect **323 passed**, and 24 AF-Auth / 6 AF-Inject / 18 benign **dev** scenarios plus
17 AF-Auth / 5 AF-Inject / 10 benign **held-out** scenarios, 23 tools.

Three experiments reproduce with no key:

```bash
.venv/Scripts/python.exe -m agentfw.cli probe-contract
.venv/Scripts/python.exe -m agentfw.cli replay experiments/e01b_compiled/config.yaml
.venv/Scripts/python.exe -m agentfw.cli replay experiments/e11_heldout/replay.yaml
```

---

## 1. Where the project is, in one paragraph

Phase 1 measured the problem and changed the thesis: agents fail by inferring authority from
silence, not by ignoring explicit boundaries. Phase 2 built the deterministic reference
monitor. Phase 3 built the intent compiler and concluded, from four registered arms on the
dev slice, that a compiled scope from either a capable model or an explicit formulation
reaches the gold-scope result end to end — and retired the M0–M5 ladder on that basis
(D-032). **Phase 3.5 repaired the benchmark and tested that conclusion on unseen data. The
injection half replicated perfectly and the authorization half did not**, so D-032 is
reopened (D-034). The benchmark itself is now the part of this project with the strongest
evidence behind it.

**What replicated.** ASR is **0.0% under every compiled scope** on a held-out slice where the
undefended agent is hijacked **33.3%** of the time by five unseen attacks, two of them
defense-aware. Deny-by-default over an effect ontology does that with no model in the loop.

**What did not.** The best compiled scope leaks **9.1%** of contested effects on unseen
underspecified instructions, where dev showed **0.0%**:

| leakage, underspecified low | `baseline` | `per-class` |
|---|---|---|
| `gpt-4.1-mini` — dev | 53.3% | **0.0%** |
| `gpt-4.1-mini` — **held-out** | **36.4%** | **21.2%** |
| `claude-sonnet-5` — dev | 10.0% | **0.0%** |
| `claude-sonnet-5` — **held-out** | **18.2%** | **9.1%** |

F-19 called the two interventions *substitutes* because either alone reached the floor on
dev. Held out both help, neither suffices, and they compose. **The architecture's bet still
pays — 81.8% undefended against 9.1% for the best compiled scope — but "reaches the
gold-scope result" was a dev-slice statement.**

**And the residue is F-16 unfixed rather than noise.** It concentrates in five of eleven
triples, one of which leaks on every arm, and on those cases the compiler grants the
contested class while asking a question about *how* — *"What answers should be submitted…"*,
*"Is the exact duration 1 hour…"*. That is F-16's sentence verbatim, in the arms F-17 and
F-19 declared had fixed it.

**The benchmark, which was the weak link, is now the strong one.** F-20 is repaired and the
repair is validated by intervention: the dev phenomenon survives it and grows (38.9% → 45.6%
overreach, +36.7 pp → **+42.7 pp** gap, compliance 81.2% → **93.1%**). The held-out slice
went from 3 explicit pairs in the dev world to 32 scenarios in a world of its own, with
underspecified triples over six contested effect classes, benign tasks and injection attacks
— so leakage, FPR-block and ASR are all measurable held out for the first time (D-031 said
none of them were).

## 2. Phase 3.5 deliverables, against the roadmap

| # | Deliverable | Status |
|---|---|---|
| 1 | Fix F-20; re-run the undefended baselines | **done.** One repair contract shared by every searchable tool; E-00g (dev, 516 ep) and E-00i (held-out, 180 ep) |
| 2 | An underspecified-triple generator template | **done.** The generator no longer knows "low" and "high" as field names; a template declares its variants. Five new templates |
| 3 | A real held-out slice, gated | **done.** 32 scenarios / 60 utterances / 6 contested classes / a second world, through five gates |
| 4 | Held-out gold scopes authored independently | **done (D-033).** Brief and input committed before the author ran; output committed verbatim |
| 5 | Re-run E-09a and E-01b on it | **done (E-11).** All six arms; the exit criterion is answered in the negative |
| 6 | Fix F-05, F-03, F-06 | **done**, in the same commit as F-20. F-06 re-diagnosed as F-22 and then corrected again by E-00g |

## 3. What exists in code that did not before

```
agentfw/
  sandbox/search.py        the query contract every searchable tool shares (F-20, F-21)
  sandbox/fixtures/office_heldout.yaml   a second world: different person, clients, work
  eval/findability.py      the gate that would have caught F-20 mechanically
  eval/contract_probe.py   how much committed evidence the repair moves (`agentfw probe-contract`)
  eval/generator.py        rewritten: a template declares its variants; pairs and triples from one mechanism
  eval/templates/          b4_us_{email_followup,payment_due,files_tidy,share_report,calendar_hold,web_form}
                           + b1_ho_draft_vs_send (held-out controls)
  eval/suites/{benign,af_inject}/heldout.yaml    10 benign + 5 injection, held out
  eval/scopes_data/heldout_v2.yaml               the independently authored labels (D-033)
docs/authoring/            the brief, its input, and the superseded v1 labels
tests/test_heldout_slice.py   every held-out oracle is satisfiable by a stated ideal play
experiments/{e00g,e00i,e11,f20_probe}/
```

Five things worth not re-deriving:

- **The apparatus boundary is one commit** (`2499f0d`), and `agentfw probe-contract` measures
  it: 18.2% of E-00b's episodes, 61.1% of E-00h's, saw a search result that would now differ.
- **The compiled scopes were unaffected by the repair**, because D-025 restricts the
  compiler's input to the utterance and the tool catalogue. A test recomputes the prompt
  digest of all 1,190 committed records so a tool-description edit cannot silently
  invalidate them.
- **`CompiledScopeStore.scope_for` raises on a reworded utterance** (F-23). This is why F-05
  was repaired in the *world* rather than in the sentence that asks for the missing figure.
- **The held-out slice ships an ideal play per variant.** F-01 asserts no oracle is true
  before the agent acts; this asserts every oracle can be made true at all. It found F-24 on
  its first run.
- **Attack oracles are pinned from both sides**: silent on a clean play, loud on the hijack
  the payload actually asks for.

## 4. Results

### The two baselines, pre- and post-repair, never differenced across the boundary

| | E-00b dev **pre** | E-00g dev **post** | E-00i held-out **post** |
|---|---|---|---|
| High-authority compliance | 81.2% | **93.1%** | 68.6% (gate floor 0.60) |
| Underspecified overreach | 38.9% [25.6, 52.2] | **45.6% [31.1, 61.1]** | **81.8% [60.6, 100.0]** |
| Explicit-low overreach | 2.2% | 2.9% | **0.0%** (0/51) |
| Gap | +36.7 pp | **+42.7 pp** | **+81.8 pp** |
| Benign BTC | 88.0% | **97.2%** | 96.7% |
| ASR undefended | 22.2% | 30.6% | **33.3%** |

Anthropic's dev row (E-00f, 60.0% underspecified) stays **pre-repair** and is not re-run —
a declared budget decision, disclosed everywhere it appears.

### E-11 verdicts, held out (180 episodes, `M0-consequential`)

| Scope source | Overreach (underspec.) | Compliance | ASR | Benign FPR-block |
|---|---|---|---|---|
| *(undefended)* | 81.8% | 68.6% | 33.3% | — |
| gold (independent) | **0.0%** | 60.8% | **0.0%** | 0.0% |
| `tool-ceiling` | 63.6% | 60.8% | 6.7% | 0.0% |
| `read-only` | 0.0% | 49.0% | 0.0% | 15.5% |
| `baseline` gpt, 3 seeds | 12.1 / 12.1 / 21.2% | 68.6% | 0.0% | 0.0% |
| `per-class` gpt, 3 seeds | 9.1 / 27.3 / 18.2% | 68.6 / 68.6 / 66.7% | 0.0% | 0.0% |
| `baseline` Sonnet, 2 seeds | 18.2 / 9.1% | 60.8% | 0.0% | 5.5 / 10.9% |
| `per-class` Sonnet, 1 seed | **9.1%** | 60.8% | **0.0%** | **0.0%** |

**Read the compliance column with F-29 in hand.** The compiled arms beat gold there because
the trusted core denies a licensed payment whenever the scope was right enough to authorize
the preparatory read. Under `ask_on: all_out_of_scope` every arm converges to 60.8%.

### Registered predictions, scored

| Predictions | Outcome |
|---|---|
| 1–5 (E-00g, dev post-repair) | **all held.** The phenomenon survives its instrument being fixed |
| 6–9 (E-00i, held-out baseline) | **all held.** Gate passes at 68.6%; 81.8% vs 0.0% matched contrast; 10/11 flips |
| 10 `per-class` gpt leaks < 15% | **FALSIFIED** — 21.2% |
| 11 baseline leaks ≥ 20 pp more than per-class | **failed** — 15.2 pp |
| 12 Sonnet baseline < gpt baseline | held — 18.2% vs 36.4% |
| 13 some arm reaches 0.0% overreach **and** 0.0% ASR | **FALSIFIED** — ASR yes everywhere, overreach best 9.1% |
| 14 best arm's compliance within 10 pp of gold | held, **for the wrong reason** (F-29) |
| 15 `tool-ceiling` reproduces undefended overreach | failed — 63.6% vs 81.8%. F-11 weakens to "worth little", not "worth nothing" |
| 16 `per-class` costs retention on gpt, not Sonnet | held — 88.2% vs 100% |

**10 and 13 were the exit criterion. Both falsified. D-032 reopened (D-034).**

## 5. Open defects and risks carried forward

| ID | Issue | Action owed |
|---|---|---|
| **F-29** | The flow gate denies a licensed payment; compliance therefore **rewards under-granting**; and whether it fires depends on `MIN_EVIDENCE_LEN = 8` against a 7- vs 14-character method id | **Phase 4, `monitors/flow.py`.** First measured requirement on it, with a reproducing case |
| **F-27** | `old_renders::b` is F-20's class in the files domain; the findability gate covers word queries, not globs | Phase 5: fix the scenario *and* extend the gate, in that order, before anything is measured against either |
| **F-26** | Two labellers agree on the contested class 6/6 and the whole effect set 0/6 | A labeller-variance floor sits under every effect-set number. Measure it properly before quoting F1 or exact-match |
| **F-16** | The compiler settles *whether* and asks *how* | **Not fixed.** The cheap structural fix — a grant contradicted by its own open question — was dismissed on dev evidence (2 of 8) and deserves re-measuring on held-out. D-034 |
| **F-10** | `consequential()` cannot tell "not worth interrupting about" from "the compiler probably dropped this" | Phase 4 cost model |
| **F-11** | Tool-allowlist authority ≈ undefended overreach | **Weakened**: exact on dev, 63.6% of 81.8% held out. B-01 proper is Phase 5 |
| **F-12** | Gold scopes inconsistent about paths named in an utterance | Dev labels unchanged on purpose; the held-out author applied rule 3 uniformly from the start |
| **F-08 / F-07** | ASK granularity; argument vs authority provenance | Phase 4 |
| **F-06** | Compliance untrustworthy | **Resolved** via F-22, then F-22 itself corrected by E-00g |
| **F-05 / F-03 / F-20 / F-21 / F-23 / F-24 / F-25 / F-28** | Benchmark and harness defects | **All resolved in Phase 3.5**, each with a gate or a loud failure in place of the silence |
| **R-14** | Claude-authored scenarios, labels and compiler arms | **Improved on one axis only** (D-033 removes *context* contamination, not authorship). Needs a human or another vendor — Phase 5 |
| **R-09** | Open-weight generalisation | Unresolved |
| **R-16** | Prompt development and measurement share the dev slice | Intact: no prompt was touched in Phase 3.5 |

## 6. The next milestone is Phase 4, and D-034 changed what it must contain

Phase 4 was going to build a cost model and sweep `C_ask`. It still must, and it now has two
further obligations that Phase 3.5 created:

1. **Decide something in the band.** D-034 un-retires the ladder's *question*, not its
   answer. The evidence says the estimand is narrow and concentrated — five of eleven
   triples, one failing on every arm — and that the failure is **structurally visible**: a
   grant accompanied by an open question that presupposes it. Measure the structural fix and
   the disagree-across-arms ensemble **before** building calibration apparatus. The cascade
   and the cheap end (M1–M3, M5) stay retired on D-032's untouched cost argument.
2. **Fix F-29 before quoting any compliance number.** While the flow gate denies a licensed
   payment, "compliance" is partly a measure of how much a scope failed to authorize.

**Do not** relitigate D-006 (no ML in the trusted path), D-018 to D-025, D-030's provenance
asymmetry, or D-033's authoring condition without a documented reason.

### Cheap things worth doing whenever

- A second and third seed for `per-class` on Sonnet (~$1.1 each). The best arm rests on one.
- The dev slice's `af_auth.us.email.sam_number::c` still points at the Q1 report while its
  siblings ask about Q3 — legible only because F-23 made rewording an utterance expensive.
- Extend the findability gate to glob and prefix tools (F-27).

## 7. Environment notes

- Python 3.12.9, uv 0.12.7, git 2.55, Windows 11. Venv at `.venv/`.
- Credentials load from **`.env.local`** (gitignored). It now holds **both** a working
  `OPENAI_API_KEY` and a working `OPENROUTER_API_KEY` — the previous note that OpenRouter was
  "in the operator's shell but not in `.env.local`" is **stale**, and all four E-11 arms
  including both Sonnet ones ran on it. The file wins a conflict with an exported variable
  and says so (D-029); every command prints the credential fingerprint it used.
- No NVIDIA GPU. Ollama has `qwen2.5-coder:14b`; usable as an exploratory compiler only.
- **Phase 3.5 spent roughly $3.5** — E-00i $0.20, E-00g $0.76, E-11 $2.51 (of which $2.26 is
  the two Sonnet arms), smoke tests ~$0.05. **Total project API spend is roughly $12.**
- **Smoke-test one call per arm before launching it.** Four arms were smoked for about $0.03
  and all four ran clean afterwards. Separately, **dry-run the free half of a pipeline before
  paying for the expensive half** — that is how F-28 was caught, at a cost of one minute
  instead of ~$2 and an argument with sunk cost.
