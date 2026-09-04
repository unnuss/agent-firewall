# PRE-REPAIR — measured under the Phase 1-3 tool contract

Everything in this directory was produced **before** the Phase 3.5 apparatus repair
(commit "Phase 3.5: the apparatus repair", 2026-09-04). It is correct as reported and it
is not superseded, corrected or re-scored. It is simply measured on a different
instrument, and these numbers may not be differenced against any post-repair number.

**What changed underneath.** `email_list` and `contacts_search` matched a contiguous
substring of two metadata fields, so the way people name people --- "Dana Whitfield",
"Cloudhost billing" --- returned nothing and a competent agent correctly gave up (F-20).
`storage_list` answered "Bucket is empty." for a prefix that merely failed to match, which
was false (F-21). Three benchmark defects were repaired in the same commit: a scenario
asking for a figure the world did not contain (F-05), a benign oracle demanding a body read
the task did not require (F-03), and a newsletter no utterance's wording could find (F-06).

**How much of *this* run it touches**, measured rather than asserted:

| Episodes | Searches replayed | Searches that would now differ | Episodes touched |
|---|---|---|---|
| 516 | 477 | 127 | **94** (18.2%) |

Regenerate with `agentfw probe-contract`; the authoritative output is
`experiments/f20_probe/results/probe.md`.

The post-repair replacements are E-00g (dev) and E-00i (held-out). See the Phase 3.5
registration in `docs/EXPERIMENTS.md`.
