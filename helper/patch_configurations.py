"""Orchestrate the per-app patchers from the active theme.

Holds no patching logic of its own: each application is patched by its own
``helper/patch_<app>.py``, and this module is the registry that runs them, the failure
isolation around them, and the "apply the theme now" script under ``__main__`` that also
reloads the running programs. Invoked when the theme is switched or the palette is
regenerated.
"""

import argparse
import contextlib
import json
import os
import signal
import subprocess
import sys
from collections.abc import Callable
from typing import Any

#: This file's repository, resolved through any symlink used to invoke it.
_REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

try:
    from helper.patch_dunst import patch_dunst
    from helper.patch_gtk import patch_gtk
    from helper.patch_kitty import patch_kitty
    from helper.patch_lock import patch_lock
    from helper.patch_plymouth import install_system as install_boot_splash
    from helper.patch_qutebrowser import patch_qutebrowser
    from helper.patch_rofi import patch_rofi
    from helper.patch_starship import patch_starship
    from helper.patch_tmux import patch_tmux
    from helper.patch_web_greeter import install_system as install_login_screen
    from helper.patch_web_greeter import patch_web_greeter
    from helper.patch_xorg import patch_xorg
    from helper.utils import logger
except ImportError:
    # Reached when this file runs as a script: sys.path[0] is then helper/, not the
    # repository root, so the package-qualified form cannot resolve. Both branches land on
    # the same modules; see helper/README.md.
    from patch_dunst import patch_dunst
    from patch_gtk import patch_gtk
    from patch_kitty import patch_kitty
    from patch_lock import patch_lock
    from patch_plymouth import install_system as install_boot_splash
    from patch_qutebrowser import patch_qutebrowser
    from patch_rofi import patch_rofi
    from patch_starship import patch_starship
    from patch_tmux import patch_tmux
    from patch_web_greeter import install_system as install_login_screen
    from patch_web_greeter import patch_web_greeter
    from patch_xorg import patch_xorg
    from utils import logger


def reload_kitty() -> None:
    """Make every running kitty re-read the configuration just written.

    ``patch_kitty`` sets ``auto_reload_config``, and kitty does watch the file -- but a theme
    switch that relied on that alone left terminals on the previous palette often enough to be
    reported as "the migration did not refresh kitty". SIGUSR1 is what kitty's own
    ``reload_conf_in_all_kitties()`` sends, so this is the mechanism rather than a nudge.

    Not `kitty +kitten themes --reload-in=all`, which reloads but also rewrites kitty.conf to
    add an ``include`` and leaves a kitty.conf.bak beside it -- inside the repository, since
    ~/.config/kitty is a symlink to it.
    """
    try:
        result = subprocess.run(
            ["pgrep", "-x", "kitty"], capture_output=True, text=True, check=False
        )
    except OSError:
        logger.info("pgrep is unavailable; kitty was not reloaded ...")
        return
    pids = [pid for pid in result.stdout.split() if pid.isdigit()]
    if not pids:
        return
    for pid in pids:
        with contextlib.suppress(OSError, ValueError):
            os.kill(int(pid), signal.SIGUSR1)


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
    ("lock", patch_lock),
    ("tmux", patch_tmux),
    ("starship", patch_starship),
    ("dunst", patch_dunst),
    ("gtk", patch_gtk),
    ("web-greeter", patch_web_greeter),
    ("qutebrowser", patch_qutebrowser),
)


#: The patchers that write outside ``~`` and so need root: each renders its theme for the
#: configuration, installs it under the active theme's name and makes it the one in use.
#: Not part of ``patch_all``, which runs unattended on every light/dark switch; these run when
#: the theme itself changes, through ``install.py --system``. Same shape for both:
#: ``(configuration, *, prompt) -> bool``.
SYSTEM_PATCHERS: tuple[tuple[str, Callable[..., bool]], ...] = (
    ("login screen", install_login_screen),
    ("boot splash", install_boot_splash),
)


def install_system(configuration: dict[str, Any], *, prompt: bool = False) -> list[str]:
    """Run every system patcher, isolating failures. Returns the names of those that failed.

    The same contract as ``patch_all``: one that raises or reports failure is named and the
    others still run. ``prompt`` is passed through; ``install.py --system`` asks for root
    once beforehand, so with sudo neither prompts again.
    """
    failed = []
    for name, install in SYSTEM_PATCHERS:
        try:
            if not install(configuration, prompt=prompt):
                failed.append(name)
        except Exception:
            logger.exception(f"Installing the {name} failed; continuing with the rest.")
            failed.append(name)
    return failed


def patch_all(configuration: dict[str, Any]) -> list[str]:
    """Run every patcher, isolating failures. Returns the names of those that failed.

    A patcher skips the failures it can anticipate; this catches the ones it cannot. The
    breadth is the point rather than a lapse -- one raise here would otherwise leave every
    later app on the previous palette, and the contract in helper/README.md is that one
    broken app must not block the others. Nothing is swallowed: each failure is logged with
    its traceback and named in the return value.
    """
    failed = []
    for name, patch in PATCHERS:
        try:
            patch(configuration)
        except Exception:
            logger.exception(f"Patching {name} failed; continuing with the remaining apps.")
            failed.append(name)
    if not patch_vsc_subprocess(configuration):
        failed.append("vscode")
    return failed


def patch_vsc_subprocess(configuration: dict[str, Any]) -> bool:
    """Patch VSCode, which runs as a subprocess rather than a registry entry.

    It takes CLI arguments, and keeping it out of ``PATCHERS`` keeps the heavyweight ``colour``
    import off the path of the nine patchers that do not need it.

    Called from ``patch_all`` rather than from ``reload_applications``, where it used to live.
    That put it on the one path ``install.py`` does not take: installing and migrating both call
    ``patch_all`` alone, so VSCode kept the palette of whatever theme had been installed before
    -- visibly, and only in VSCode, which reads as an application problem rather than a missing
    step. Patching is also the right phase for it: it writes a file, it does not reload anything.
    """
    result = subprocess.call(
        args=[
            sys.executable,
            os.path.join(_REPOSITORY_ROOT, "helper", "patch_vsc.py"),
            "--mode",
            configuration["state"]["theme"],
            "--input-path",
            os.path.join(_REPOSITORY_ROOT, "configuration", "vscode"),
        ]
    )
    if result != 0:
        logger.warning(f"Patching vscode exited {result}; it keeps the previous palette.")
    return result == 0


def reload_applications(configuration: dict[str, Any]) -> None:
    """Make the running programs pick up what the patchers just wrote.

    Separate from ``patch_all`` because patching is idempotent and safe to call from
    anywhere, while this restarts qtile and kills dunst. Anything that only wants the files
    updated calls ``patch_all`` alone.
    """
    subprocess.call(args=["killall", "dunst"])
    subprocess.call(
        args=[
            "tmux",
            "source-file",
            os.path.expanduser(os.path.join("~", ".config", "tmux", "tmux.conf")),
        ]
    )
    reload_kitty()
    reload_qutebrowser()
    subprocess.call(args=["qtile", "cmd-obj", "-o", "cmd", "-f", "restart"])


def report(failed: list[str]) -> None:
    """Tell the desktop what happened, since nothing is watching this script's output."""
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


def main(argv: list[str] | None = None) -> int:
    """Apply the active theme now: patch every app, reload them, report."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help=(
            "rewrite the configurations without reloading the running programs. Used by the "
            "monitor hotplug hook, which reloads qtile itself: reloading from here would "
            "restart qtile, which is what the hook is already doing."
        ),
    )
    arguments = parser.parse_args(argv)

    with open(os.path.expanduser("~/.config/config.json")) as input_handle:
        configuration = json.load(input_handle)
    failed = patch_all(configuration)
    if not arguments.no_reload:
        reload_applications(configuration)
        report(failed)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
