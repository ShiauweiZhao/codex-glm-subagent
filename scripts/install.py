#!/usr/bin/env python3
"""Source-tree launcher for the codex-glm-subagent installer.

Adds the repository ``src`` directory to ``sys.path`` so the scoped package is
importable, then invokes ``installer.main``.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from codex_glm53_subagent import installer  # noqa: E402


def main() -> int:
    return installer.main()


if __name__ == "__main__":
    sys.exit(main())
