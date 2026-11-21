"""The qtile configuration, on two monitors that are regions of one virtual display.

A virtual display has one output, so qtile would find one screen however many monitors the
staged configuration lists. This runs the real ``config.py`` unchanged and then tells qtile
where its screens are, side by side in the order ``config.py`` built them. Nothing here
configures anything: every bar, binding and colour is the real file's.
"""

import json
import os
import sys

REAL = os.path.expanduser("~/.config/qtile/config.py")

# qtile puts the directory of the file it loads on the path, which is this one's; the real
# configuration imports its widgets relative to its own.
sys.path.insert(0, os.path.dirname(os.path.realpath(REAL)))
__file__ = REAL
with open(REAL, encoding="utf-8") as handle:
    exec(compile(handle.read(), REAL, "exec"))  # noqa: S102 -- the real configuration, by path

with open(os.path.expanduser("~/.config/config.json"), encoding="utf-8") as handle:
    monitors = json.load(handle)["monitors"]

fake_screens = screens  # noqa: F821 -- defined by the configuration executed above
offset = 0
for screen, name in zip(
    fake_screens, sorted(monitors, key=lambda name: monitors[name]["is_primary"], reverse=True),
    strict=True,
):
    screen.x, screen.y = offset, 0
    screen.width, screen.height = monitors[name]["width"], monitors[name]["height"]
    offset += screen.width
