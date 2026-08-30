# E-00c — result provenance

**Status: INCONCLUSIVE (failed the pre-registered competency floor). Preserved as a
historical run. Do not re-run, edit, or fold into E-00d.**

Run 2026-08-29 on Kaggle, 2×T4, `Qwen/Qwen3-8B` served by vLLM. 186/186 episodes usable,
no provider or parser failures.

| Metric | Value |
|---|---|
| Underspecified OR | 17.8% [4.4, 35.6] (8/45) |
| Explicit-low OR | 1.4% [0.0, 4.3] (1/69) |
| Matched-pair contrast | 19.0% underspecified vs 0.0% explicit |
| Ambiguity-only flips | 4/14 matched scenarios |
| Scenario incidence | 4/15 underspecified vs 1/23 explicit |
| Overall OR | 7.9% |
| **High-authority compliance** | **31.9% [15.3, 50.0]** — floor is 60% |

## Why the numbers above are not evidence

Compliance is roughly half the pre-registered floor. About two thirds of high-authority
episodes failed to produce the contested effect even when the user explicitly asked for it.
An agent that often fails to act produces low rates everywhere, and the explicit-low
denominator is exactly where that failure is indistinguishable from correct restraint — so
the apparent gap is confounded with incapability *in the direction that flatters our
hypothesis*. Full reasoning in `docs/EXPERIMENTS.md`, section E-00c.

## Raw data

**The episode log for this run is not in the repository.** These figures were reported from
the Kaggle session summary. To make E-00c fully reproducible, copy `episodes.jsonl` (and
`traces/` if kept) from that session into this directory; `agentfw report
experiments/e00c_openweight/results` will then regenerate `report.md` with the competency
gate rendered automatically.

Until that happens, treat this file — not a regenerated report — as the record, and note
that the figures have not been independently recomputed from raw episodes on this machine.
