# E-00d — result provenance

**Status: INCONCLUSIVE (failed the pre-registered competency floor). Preserved as a
historical run. Do not re-run, edit, or fold into E-00e.**

Run 2026-08-29 on Kaggle, 2×T4, `Qwen/Qwen3-14B-AWQ` served by vLLM.

| Metric | Value |
|---|---|
| **High-authority compliance** | **36.1%** — floor is 60% |
| Verdict | INCONCLUSIVE |

## What it showed

Compliance moved 31.9% → 36.1% for roughly double the parameters. Two models, two sizes,
two precisions, both far short of the floor. That slope is what motivated D-020: the
binding constraint is free-tier hardware capability, not a missing model family.

The AWQ confound (R-12) resolved in the uninformative direction that was predicted in
advance — a sub-floor result cannot separate "family-specific" from "too weak" from
"quantization broke instruction-following". E-00d says nothing about cross-family
generalisation.

## Raw data

**The episode log for this run is not in the repository**, as with E-00c. The compliance
figure was reported from the Kaggle session summary and has not been recomputed from raw
episodes on this machine. If the session is recoverable, copy `episodes.jsonl` here and
`agentfw report experiments/e00d_openweight_14b/results` will regenerate the full report
with the competency gate rendered.
