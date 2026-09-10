"""The learned intent compiler (Phase 6, E-15).

**This package is outside the trusted computing base and it is optional.** Nothing here is
imported by `agentfw/core/`, by `agentfw/policy/`, or by the firewall assembly, and a test
asserts it. `pip install agentfw` still installs the TCB with `pydantic` and `pyyaml` alone;
everything in this package that needs `scikit-learn`, `torch` or `transformers` imports them
lazily, inside the function that uses them, so that `import agentfw.ml` works without the
`ml` extra and fails with a sentence rather than a traceback when a rung is actually run.

**What it is allowed to do** (D-041, under D-006). Two arms, one model:

* **Arm L** emits a `CompiledScope` exactly as `LLMIntentCompiler` does. The compiler slot
  has never been in the TCB — the scope it produces is the *starting* authority, and
  monotonicity still means only a human can widen it. A prompted frontier model already
  occupies this slot and produced every compiled number in the project.
* **Arm H** may only *withhold* classes an existing scope granted. It cannot add one.

**What it may never do.** Emit `Signal(structural=True)`, read a scenario id as a feature, or
be trusted more than a prompted scope is. All three are tested, not remembered.
"""

from __future__ import annotations

__all__ = ["dataset", "splits"]
