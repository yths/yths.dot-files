"""Make the repository's own modules importable.

Nothing here is a package: qtile puts ``configuration/qtile`` on ``sys.path`` at startup and
the helpers run as scripts from ``helper/``. Tests import them the same way rather than
inventing a packaging layout that production never uses.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

for path in (REPO_ROOT, REPO_ROOT / "helper", REPO_ROOT / "configuration" / "qtile"):
    sys.path.insert(0, str(path))
