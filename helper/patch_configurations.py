"""Orchestrate the per-app patchers from the active theme.

Holds no patching logic of its own: each application is patched by its own
``helper/patch_<app>.py``, and this module is the registry that runs them, the failure
isolation around them, and the "apply the theme now" script under ``__main__`` that also
reloads the running programs. Invoked when the theme is switched or the palette is
regenerated.

Six of these patchers used to live in this file as functions while three had modules of
their own, so ``helper/README.md`` documented a layout most of them did not follow and the
orchestrator both orchestrated and implemented.
"""

import json
import os
import subprocess
import sys
from collections.abc import Callable
from typing import Any

#: This file's repository, resolved through any symlink used to invoke it.
_REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

try:
    from helper.patch_dunst import patch_dunst
    from helper.patch_kitty import patch_kitty
    from helper.patch_rofi import patch_rofi
    from helper.patch_starship import patch_starship
    from helper.patch_tmux import patch_tmux
    from helper.patch_web_greeter import patch_web_greeter
    from helper.patch_xorg import patch_xorg
    from helper.utils import logger
except ImportError:
    # Reached when this file runs as a script: sys.path[0] is then helper/, not the
    # repository root, so the package-qualified form cannot resolve. Both branches land on
    # the same modules; see helper/README.md.
    from patch_dunst import patch_dunst
    from patch_kitty import patch_kitty
    from patch_rofi import patch_rofi
    from patch_starship import patch_starship
    from patch_tmux import patch_tmux
    from patch_web_greeter import patch_web_greeter
    from patch_xorg import patch_xorg
    from utils import logger


def reload_qutebrowser() -> None:
    """Send SIGHUP to every running qutebrowser so it picks up the new palette.

    This used to be ``subprocess.call(["kill", "-1", "`pgrep qutebrowser`"])``. With a list
    argument there is no shell, so the backticks were passed to ``kill`` literally rather
    than being command-substituted; the call failed every time and its non-zero exit was
    discarded, so qutebrowser was never actually reloaded on a theme change.
    """
    try:
        result = subprocess.run(
            ["pgrep", "qutebrowser"], capture_output=True, text=True, check=False
        )
    except OSError:
        logger.info("pgrep is unavailable; qutebrowser was not reloaded ...")
        return
    pids = [pid for pid in result.stdout.split() if pid.isdigit()]
    if not pids:
        return
    subprocess.call(args=["kill", "-1", *pids])


#: Every patcher ``patch_all`` runs, with the name reported when one fails. One entry per
#: ``helper/patch_<app>.py``. Order is not load-bearing -- they write to disjoint targets --
#: so a new patcher is one import and one row.
PATCHERS: tuple[tuple[str, Callable[[dict[str, Any]], None]], ...] = (
    ("rofi", patch_rofi),
    ("xorg", patch_xorg),
    ("kitty", patch_kitty),
    ("tmux", patch_tmux),
    ("starship", patch_starship),
    ("dunst", patch_dunst),
    ("web-greeter", patch_web_greeter),
)


def patch_all(configuration: dict[str, Any]) -> list[str]:
    """Run every patcher, isolating failures. Returns the names of those that failed.

    A patcher skips the failures it can anticipate, but an unanticipated one used to escape
    into this loop and cancel every patcher after it: a single raise in the first of seven
    left kitty, tmux, starship, dunst and web-greeter on the previous palette, silently.
    Catching broadly here is the point rather than a lapse -- the contract in
    helper/README.md is that one broken app must not block the others -- and nothing is
    swallowed: each failure is logged with its traceback and named in the return value.
    """
    failed = []
    for name, patch in PATCHERS:
        try:
            patch(configuration)
        except Exception:
            logger.exception(f"Patching {name} failed; continuing with the remaining apps.")
            failed.append(name)
    return failed


if __name__ == "__main__":
    # Everything below is the "apply the theme now" script: it rewrites every app's
    # config, reloads the running programs and restarts qtile. It sits behind the
    # guard so that importing this module -- to call a single patcher, or to test one
    # -- does not fire the whole sequence as a side effect.
    with open(os.path.expanduser("~/.config/config.json")) as input_handle:
        configuration = json.load(input_handle)
    failed = patch_all(configuration)

    subprocess.call(args=["killall", "dunst"])
    subprocess.call(
        args=[
            "tmux",
            "source-file",
            os.path.expanduser(os.path.join("~", ".config", "tmux", "tmux.conf")),
        ]
    )
    subprocess.call(
        args=["kitty", "+kitten", "themes", "--reload-in=all", configuration["name"]]
    )
    reload_qutebrowser()
    subprocess.call(
        args=[
            "python",
            os.path.join(_REPOSITORY_ROOT, "helper", "patch_vsc.py"),
            "--mode",
            configuration["state"]["theme"],
            "--input-path",
            os.path.join(_REPOSITORY_ROOT, "configuration", "vscode"),
        ]
    )
    subprocess.call(args=["qtile", "cmd-obj", "-o", "cmd", "-f", "restart"])
    if failed:
        subprocess.call(
            args=[
                "notify-send", "-u", "critical", "Patching",
                f"Reloaded, but these were not patched: {', '.join(failed)}",
            ]
        )
    else:
        subprocess.call(
            args=["notify-send", "-u", "normal", "Patching", "All configurations reloaded ..."]
        )
    sys.exit(1 if failed else 0)
