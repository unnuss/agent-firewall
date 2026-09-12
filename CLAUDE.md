# Working agreement for Claude Code sessions on this project

## Read order at the start of every session
1. `PROJECT_STATE.md` — where we are, what is next, open questions, risks.
2. `docs/DECISIONS.md` — do not relitigate an accepted decision without a reason.
3. `docs/ROADMAP.md` — the current phase's deliverables and exit criteria.
4. Whichever of `docs/ARCHITECTURE.md` / `docs/EVALUATION.md` / `docs/THREAT_MODEL.md`
   the current work touches.

## Rules of engagement

- **One phase per session.** Do not begin the next major milestone without being asked.
- **End every phase with:** tests run, docs updated (`PROJECT_STATE.md` always;
  `EXPERIMENTS.md` if anything was measured; `DECISIONS.md` if anything was decided),
  a written summary, unresolved problems named, and the next milestone stated.
- **Never fabricate a number.** If an experiment was not run, its result is `(pending)`.
  If a run failed, say so with the output.
- **Negative results are deliverables.** E-01 has a registered prediction that may be
  unflattering to the architecture. Publish it either way (D-012).
- **The ML stays outside the TCB** (D-006). If a proposed change lets a model grant
  authority, it is wrong regardless of how well it performs.
- **Scope is defended, not expanded.** `PROJECT_SPEC.md` section 7 lists what is out of
  scope. Adding multi-agent, memory poisoning, or computer-use is how this project dies.
- **No AI attribution in commits, ever.** Commit messages carry no `Co-Authored-By`,
  `Generated-By`, `Assisted-By` or "Generated with" trailer, and the author and committer are
  always Unnus Ahmad Usmani. This is a deliberate ownership decision for a portfolio repository,
  not an oversight, and it is enforced at two levels: this rule, and
  `includeCoAuthoredBy: false` in `.claude/settings.json`. Three such trailers were stripped from
  local history on 2026-09-12 before the first push; if any reappear, remove them before pushing.
  **Prose that discusses Claude is a different thing and must be preserved** — R-14 is literally
  the risk that scenarios and labels are Claude-authored, and deleting those sentences would
  corrupt the record.
- **Prefer deleting a component to adding a heuristic.** If something fails, log a finding;
  do not patch it with a special case that will be indistinguishable from hardcoded demo
  logic later.

## Invariants added in Phase 2 — do not weaken these

- **No ML component may emit `Signal(structural=True)`.** The combinator ignores
  non-structural signals when deciding to BLOCK, and a test asserts it. This is D-006 as a
  type rather than a paragraph.
- **`ToolRouter.declare` must never be used to authorize.** It returns `[]` on failure,
  which under deny-by-default authorizes vacuously. Authorization uses `declare_for`, which
  raises, and gate G0 turns any failure into a BLOCK.
- **An audit event records `policy_verdict` and `verdict` separately.** The first replays
  from the recorded inputs; the second depends on what a human answered and does not.
- **Gold scopes are labels, not logic.** Nothing in `agentfw/core/` may read a scenario id.

## Code conventions (from Phase 1 onward)

- Python 3.12, `uv` for environments, pydantic v2 for all core types, pytest + hypothesis,
  ruff for lint/format.
- No agent frameworks (D-002). No new dependency without a line in `DECISIONS.md`.
- Every module in `agentfw/core/` is TCB code: deterministic, no network, no model calls,
  fully unit-tested, property-tested where a security property is claimed.
- Experiment configs are YAML under `experiments/`; results are written as JSON/parquet
  next to them and never edited by hand.
- Every table in the README must be regenerable by one command.

## Things that would make this project fail, in order

1. Making indirect prompt injection the headline (D-001).
2. A hand-tuned weighted risk score (D-005).
3. Hardcoded scenario-specific logic that makes the demo look good.
4. Skipping E-00 and discovering in Phase 5 that agents rarely overreach.
5. Scenario authoring left until Phase 5.
6. A dashboard that animates decisions rather than replaying real audit logs.
