"""The command line behind the screenshot keys: capture, save, copy, and say where it went.

Three captures, chosen by key: a region the user drags out, the focused screen, or the
focused window. qtile knows the last two exactly at the moment of the key press -- the
screen's geometry, the window's id -- so it passes them in, the way ``shared.launcher``
passes rofi its geometry. ``maim`` on its own would take the whole X screen, both monitors
at once.

Every capture is saved under the pictures directory, copied to the clipboard as an image,
and announced with a notification naming the file, so a screenshot is never only in one of
the three places. Pure: the caller reads the numbers off qtile's objects.
"""

import datetime
import os
import re
from typing import NamedTuple

#: Run by ``sh -c`` with the file as ``$1`` and maim's arguments after it, so neither has
#: to be quoted into the script. Each step runs only if the one before it succeeded: a
#: cancelled region selection makes maim fail, and nothing is copied or announced.
PIPELINE = (
    'path=$1; shift; mkdir -p "$(dirname "$path")" && maim "$@" "$path" '
    '&& xclip -selection clipboard -t image/png -i "$path" '
    '&& notify-send -i "$path" "Screenshot" "$path"'
)


class Geometry(NamedTuple):
    """A screen's size and position on the X screen, in pixels."""

    width: int
    height: int
    x: int
    y: int


def pictures_directory(home: str | None = None) -> str:
    """``XDG_PICTURES_DIR`` from ``user-dirs.dirs``, or ``~/Pictures`` if it names none."""
    home = home or os.path.expanduser("~")
    try:
        with open(os.path.join(home, ".config", "user-dirs.dirs")) as handle:
            text = handle.read()
    except OSError:
        text = ""
    found = re.search(r'^XDG_PICTURES_DIR="([^"]+)"', text, flags=re.M)
    if found:
        return found.group(1).replace("$HOME", home)
    return os.path.join(home, "Pictures")


def target_path(directory: str, now: datetime.datetime) -> str:
    """Where a capture taken at ``now`` is saved."""
    return os.path.join(directory, "Screenshots", now.strftime("%Y-%m-%d_%H-%M-%S.png"))


def capture_command(
    kind: str, path: str, screen: Geometry, window: int | None = None
) -> list[str]:
    """The argv that captures ``kind`` -- ``region``, ``screen`` or ``window`` -- to ``path``.

    A window capture with no focused window falls back to the screen rather than to nothing.
    The cursor is left out of every capture.
    """
    if kind == "region":
        selection = ["--select"]
    elif kind == "window" and window is not None:
        selection = ["--window", str(window)]
    else:
        selection = ["--geometry", f"{screen.width}x{screen.height}+{screen.x}+{screen.y}"]
    return ["sh", "-c", PIPELINE, "sh", path, "--hidecursor", *selection]
