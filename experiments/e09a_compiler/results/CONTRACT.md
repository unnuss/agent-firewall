# PRE-REPAIR — derived from pre-repair episodes

This directory holds *derived* results: a replay of committed episodes, or scopes compiled
from committed utterances. It carries the Phase 1-3 tool contract by inheritance and may not
be differenced against any post-repair number. See the sibling `CONTRACT.md` files under
`experiments/e00*/results/` and the Phase 3.5 registration in `docs/EXPERIMENTS.md`.

**The compiled scopes themselves are unaffected by the repair.** D-025 restricts the
compiler's input to the utterance and the tool catalogue, and neither moved: a test
recomputes the prompt digest of all 1,190 committed records whose prompt variant is current
and requires a match. What is pre-repair here is the *episodes* a replay runs over, not the
scopes it runs with.
