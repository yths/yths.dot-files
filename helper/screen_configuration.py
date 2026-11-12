"""Detect connected monitors via ``screeninfo``.

``get()`` returns a dict keyed by output name (e.g. ``HDMI-0``) with per-monitor geometry,
physical dimensions, derived DPI, diagonal, scaling factor, and ``is_primary`` flag.
Consumed by ``install.py`` to merge into the active theme bundle's ``config.json``.

The detection itself lives in ``configuration/qtile/shared/monitors.py``, because qtile needs
it on a hotplug and reaches it natively there. This is the installer's door to the same code.
"""

import json
import os
import sys

# The qtile configuration directory is on sys.path when qtile loads; it is not when this runs
# as a script. Adding it is what lets the installer and the bar share one definition of what a
# monitor's geometry is, rather than each carrying its own arithmetic.
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
        "configuration",
        "qtile",
    ),
)

import shared.monitors


def get() -> dict[str, dict]:
    """Every connected monitor, keyed by output name."""
    return shared.monitors.detect()


def main() -> int:
    print(json.dumps(get(), indent=4))
    return 0


if __name__ == "__main__":
    sys.exit(main())
