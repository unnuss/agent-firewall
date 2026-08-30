# E-00f provenance — non-canonical runs, preserved

**The canonical result is `../results/`.** Nothing in this directory is a result. These are
the failed and partial attempts that preceded it, kept because an experiment that reports
only its successful run is not auditable.

Verified 2026-08-30: `../results/episodes.jsonl` has sha256 `99bd474ee752adfb…`, matching
`FINAL_SHA256.txt`, 186/186 episodes, **zero** provider or runner errors, every episode
attributed to `anthropic/claude-sonnet-5`. A byte-identical duplicate directory
(`results_final_186of186/`) was removed after confirming hash equality — a copy is not
additional evidence.

| Artifact | Episodes | Errors | Why it is not canonical |
|---|---|---|---|
| `routing_failed_pilot/` | 3 | **3** | OpenRouter routed to an upstream that did not honour `tools`. Every episode failed at step one. This is the failure the preflight gate exists to catch, caught. |
| `rate_limited_partial/` | 37 | **24** | Rate limiting mid-run. Partial and error-contaminated. |
| `before_credit_repair/` | 186 | **24** | Full episode count but 24 episodes recorded provider errors from credit exhaustion. Reached compliance 60/72 and underspecified OR 24/45 — **the contaminated numbers are close enough to the clean ones to be dangerous**, which is exactly why it is filed here rather than left beside the real result. |
| `FINAL_SHA256.txt` | — | — | Operator-generated hashes of the canonical artifacts. |
| `FINAL_RESULT_SUMMARY.txt`, `FINAL_REPORT_CONSOLE.txt` | — | — | Operator's console capture from the final run. |

## The config change that fixed the routing failure

`extra_body.provider.{require_parameters, allow_fallbacks}` was removed from
`../config.yaml` between the failed pilot and the final run. That block pinned OpenRouter to
upstreams advertising `tools`; on this route it caused the routing failure rather than
preventing one.

This is a **provider-routing** change, not a measurement change: it alters which upstream
serves the request, not the scenarios, seeds, oracles, sampling or metrics. The final run's
zero errors and 91.7% compliance confirm the served model did native tool calling. Recorded
here so the config diff against E-00e is not mistaken for an undeclared measurement change.

## How the runner behaves under these failures

The runner is resumable and skips episodes already present in `episodes.jsonl`. That is why
partial runs accumulate rather than restarting, and why `before_credit_repair/` reached 186
rows while still carrying 24 errored episodes. `metrics.usable()` excludes
`provider_error` and `runner_error` episodes from every rate, so a contaminated file
under-reports rather than fabricating — but it under-reports silently, and the honest
handling is to quarantine the file, not to filter it and move on.
