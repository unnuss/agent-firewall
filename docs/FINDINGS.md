# Findings — the full ledger, with status

**43 findings.** Most are defects the project found in *itself*: in its own benchmark, its own
metrics, its own gates, its own conclusions. That is what the list is for. A project that only
records findings about the thing it is studying is not looking at its instrument.

`status` is one of:

| status | meaning |
|---|---|
| **live** | still true, still load-bearing. Cite freely |
| **fixed** | a real defect, repaired; kept because the repair is the evidence |
| **superseded** | later measurement replaced it. **Do not cite** |
| **narrowed** | the claim survived in weaker form than first stated |
| **open** | a defect that is *not* fixed and is owed work |

Detail for every row is in [`EXPERIMENTS.md`](EXPERIMENTS.md). Findings F-29 onward have their
own headings there; F-01…F-28 are defined inline in the phase they belong to.

---

## Phase 1 — the benchmark lying to its authors

| # | Finding | Status |
|---|---|---|
| F-01 | **Two AF-Auth oracles were satisfiable before the agent acted.** A test asserting every oracle is FALSE on an untouched world caught both | **fixed** — and became a *gate* on every generated scenario, not a review step |
| F-02 | **Conservative taint saturates immediately.** One `web_fetch` marks the remainder of the trace untrusted under a meet-over-all-ingested-spans rule | **live** — shaped the label design |
| F-03 | An over-strict benign oracle | **fixed** |
| F-04 | **A model sometimes answers without calling any tool** — a latent-knowledge shortcut that looks like task completion | **live**, harmless here, a hazard for any benchmark scored on outcomes |
| F-05 | A scenario asking for a figure the world does not contain | **fixed** |
| F-06 | Over-strict oracles made compliance untrustworthy on 8 scenarios | **fixed** |

## Phase 2 — the deterministic core, and what it could not do

| # | Finding | Status |
|---|---|---|
| F-07 | **The structural provenance rule cannot do what the architecture claimed**, and was narrowed | **narrowed** — the architecture text was corrected, not the claim quietly dropped |
| F-08 | Per-action ASK granularity floods the interruption budget on repetitive tasks | **open** — Phase 4 |
| F-09 | **ASK buys nothing when the scope is already right.** The `M0-no-ask` ablation scored identically to the default on every row, so the entire value of the ML core is bounded by compiler-versus-gold divergence | **live** — this is the finding that re-ordered Phase 3 and made E-09a urgent |
| F-10 | `consequential()` cannot distinguish "not worth interrupting about" from "the compiler probably dropped this" | **open** — Phase 4's cost model, and F-32 says fit it per contested class |

## Phase 3 — the intent compiler, and three falsifications

| # | Finding | Status |
|---|---|---|
| F-11 | **A tool-allowlist scope reproduces undefended overreach to the decimal.** Authority derived from what the tools *can* do rather than from what the user asked. Replicated three times independently | **live** — the project's strongest single control, and it superseded E-01 |
| F-12 | Moving a label after seeing a compiler's output is how the measurement stops meaning anything | **live** — the precedent later invoked to *refuse* a convenient scenario repair |
| F-13 | **The compiler invents bounds, and a wrong bound cannot be repaired by asking.** Gate G2 fired 59 times, blocking purchases the user explicitly authorised | **fixed** by D-030: an inferred bound escalates, a user-stated bound refuses |
| F-14 | **A scope-level score can rank a change that makes the deployed system worse.** Every scope metric improved and the system got much worse | **live** — the most cited finding in the repository, and it is why every compiler change must be replayed. Reversed in sign by F-38 |
| F-15 | A naive-versus-aware datetime comparison crashed inside a constraint check, removing 21 episodes from the measurement rather than deciding them. Property tests missed it; it took a model to write the breaking pair | **fixed**, fail-closed |
| F-16 | **The registered compiler licensed the contested class on 53.3% of underspecified instructions — worse than the undefended agent.** It settles *whether* and asks *how* | **live** — falsified Phase 3's central prediction and defined everything after it |
| F-17 | Changing the *formulation* moves leakage 53.3% → 0.0% | **live**, dev slice |
| F-18 | Changing the *model* moves it 53.3% → 10.0%. **How a model behaves as an agent does not predict how it behaves as a compiler** | **live** |
| F-19 | The two fixes are substitutes rather than complements | **superseded** — dev-only. At N=60 both help, neither suffices, and the interaction is unresolved |

## Phase 3.5 — the benchmark was the weak link

Nine of these ten came from **gates**, not from review. That distinction is the phase's lesson.

| # | Finding | Status |
|---|---|---|
| F-20 | **A tool contract that silently kills well-formed scenarios** — about a fifth of every episode | **fixed**, and it created the pre/post-repair apparatus boundary that no number may be differenced across |
| F-21 | A tool reporting an empty world for a missed prefix | **fixed** |
| F-22 | **A hand-read diagnosis was right about four of six — and was itself corrected by intervention** to a different sixth | **live** — reading a failure is not diagnosing it |
| F-23 | Compiled scopes keyed by id but *defined* by an utterance | **fixed** — the store now refuses a stale compilation |
| F-24 | Ten held-out scenarios silently running in the dev world | **fixed** |
| F-25 | A gate whose hardcoded probes bound it to the old world | **fixed** |
| F-26 | Two blind labellers: 6/6 on the contested class, **0/6 on the whole effect set** | **superseded** by F-31 after the brief was clarified |
| F-27 | The findability gate covers word queries, not globs | **open** — cheap, owed |
| F-28 | **A replay of the wrong split reported a perfect defense over zero episodes** | **fixed** — the replay now warns loudly on unresolved scenarios |
| F-29 | **The flow gate denies a licensed payment, so compliance rewards under-granting** — hidden for three phases behind a seven-character identifier | **open** — latent (zero denials on licensed work); Phase 4's `monitors/flow.py` |
| F-30 | A gate that infers its own targets cries wolf; the fix is for the template to declare them | **fixed** — plays now travel with the template |

## Phase 5 — N=60, and what the larger sample changed

| # | Finding | Status |
|---|---|---|
| F-31 | Residual labeller disagreement is entirely *instrumental reads*; whole-effect-set agreement went 0/6 → **48/60 (80%)** after five clarifications written while no labels existed | **live** — and 80% is the human ceiling every model number is read against |
| F-32 | **The contested effect class explains an 87.5 pp spread; the world explains 13.5 pp** — six times more variance from the class than the domain | **live** — any per-effect cost term must be fitted per class, not pooled |
| F-33 | The residual is **six utterances, not a rate**, and two of the six are probably *label* defects | **open** — fix both before anything is measured against them |
| F-34 | `per-class` does not merely grant less; it grants a **"no" the monitor can act on**. `baseline` on gpt never blocks, in 276 attempts | **live** — silence and refusal are different inputs and no design may collapse them |
| F-35 | **`read-only` is not a floor at the verdict level, and its 0.0% hides that.** 71.7% task completion, 0.798 asks/episode | **live** — the first of the four cases F-42 generalises |

## Phase 6 — the learned intent compiler

| # | Finding | Status |
|---|---|---|
| F-36 | **Leave-one-world-out overstates generalisation by 35–41 pp** — and it is the split D-038 specifically asked for, because 22 asking clauses are reused across worlds. How much is memorisation depends on the model: 24% for TF-IDF, 58% for the frozen encoder | **live** — the finding most likely to outlive this project. Do not evaluate LOWO on this benchmark |
| F-37 | **The benchmark supplies the least supervision for exactly the decision it is about**, by construction: 1 training positive for `SEND:PUBLIC_WEB` against 45 for `READ:USER_FILES` | **live** — but competence does not simply track volume |
| F-38 | **A scope-level score misranks the learned compiler by 40 points and the replay reverses it.** F-14 with the sign flipped | **live** — and it is why D-042 disqualifies scope-level adoption criteria |
| F-39 | A *trained* doubt-detector reproduces D-035's rejection of the lexical coupling rule exactly, and cannot escape it: intersection caps a filter's retention at its own recall | **live** |
| F-40 | `WRITE:USER_FILES` defeats prompted compilers by **over**-granting and the learned one by **never** granting — five compilers of two kinds, failing in opposite directions | **live** — strengthens F-33's "property of the instruction" reading |
| F-41 | The fine-tuned encoder's leakage does not fall with data (47.8% → 51.7% across a 4× increase) while retention climbs | **narrowed by E-15c** — its *mechanism* (miscalibrated weighting) is **withdrawn**: cross-validation selected the blind value |
| F-42 | **Four unrelated interventions have lowered leakage on this benchmark and all four did it by granting less.** `read-only`, Arm H's intersection, the lexical coupling rule, CV calibration. None moved off the trade-off; contrast fidelity caught every one | **live** — the most useful rule for anyone extending this work |
| F-43 | **Nineteen per-class thresholds from 48 scenarios overfit, and the out-of-fold estimate could not see it** — 45.8% OOF against 13.6% held out, because the search and the score read the same probabilities | **live** — a nested inner loop is the fix |

---

## What the shape of this list says

**Counting by subject rather than by phase:**

| what the finding is about | count |
|---|---|
| the **benchmark** being wrong, or lying to its authors | F-01, F-03, F-05, F-06, F-20, F-21, F-23, F-24, F-25, F-26, F-30, F-33 — **12** |
| a **metric** misrepresenting the system | F-14, F-35, F-38, F-42, F-43 — **5** |
| the **architecture** claiming more than it does | F-07, F-08, F-09, F-10, F-13, F-29 — **6** |
| the **phenomenon** under study | F-02, F-04, F-11, F-16, F-17, F-18, F-19, F-31, F-32, F-34, F-36, F-37, F-39, F-40, F-41 — **15** |
| **method** — how to measure this at all | F-12, F-22, F-27, F-28 — **4** |

**Twelve findings are the benchmark being wrong, and five are a metric misleading its own
author.** That is 17 of 43 — the instrument, not the result. Every one was found by a gate, a
replay, or a test that existed because an earlier finding demanded it, and none of them was
found by reviewing code and feeling confident.

**Three findings corrected an earlier finding of this project**: F-31 superseded F-26, F-38
reversed F-14's sign, and E-15c withdrew F-41's mechanism. **One corrected an instruction the
project had given itself**: F-36, against D-038's choice of split.

**Still open and owed:** F-08, F-10, F-27, F-29, F-33. Three of the five wait on Phase 4's cost
model; F-27 and F-33 are cheap and should go in the next slice that touches the benchmark.
