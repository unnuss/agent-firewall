"""Intent compilation: the user's utterance becomes an IntentScope.

This package is **outside the trusted computing base** (D-006, D-025). Nothing here can
weaken a security property: the scope it produces is the *starting* authority set for an
episode, and every invariant the firewall claims — monotonicity (P1), no effect outside
scope (P2), declassification (P3), consent integrity (P4) — holds whatever this package
emits. What a bad compiler costs is measured in the two currencies the project already
reports: unlicensed effects that reach the world (over-granting) and ordinary work that
gets refused (under-granting).
"""
