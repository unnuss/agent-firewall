"""Run the CLI as a module: ``python -m agentfw …``.

**Why this exists.** `pyproject.toml` declares an `agentfw` console script, and installers
generate a small `.exe` launcher for it on Windows. That launcher is freshly written and
unsigned, which is exactly the profile an Application Control policy blocks — on the dev
machine the generated `agentfw.exe` fails with *Permission denied* while `python.exe`, which
is signed, runs normally. Invoking the package as a module skips the launcher entirely.

It is worth having beyond that one machine: `python -m` also works when the console script is
simply not on `PATH`, which is the usual state inside CI containers, `pipx`-less installs, and
any environment where the virtualenv was not activated.

**There is no CLI logic here and there must never be any.** This module resolves the same
`agentfw.cli.main` the console script resolves and hands it the same arguments. A second
argument parser living here would drift from the first one silently, and the two entry points
would start disagreeing about what a flag means. `tests/test_entrypoints.py` asserts both that
this file delegates and that the two paths produce identical output.
"""

from __future__ import annotations

import sys

from agentfw.cli import main

if __name__ == "__main__":
    sys.exit(main())
