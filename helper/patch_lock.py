"""Patch the lock screen: its colours, font and what it is willing to display.

xsecurelock has no configuration file — it reads environment variables — so this writes the
ones the launcher sources. ``configuration/lock/lock.sh`` holds no appearance of its own, so
a theme change reaches the lock screen without editing anything.

What it deliberately does not show is as much of the point as the colours. A lock screen is
looked at by whoever walks past, so the username, the hostname and the date are all off: they
are free information about you and the machine, offered to someone you are not there to
challenge.
"""

import argparse
import json
import os
import subprocess
import sys
from typing import Any

# Resolves whether this runs as ``helper.patch_lock`` or as a script; see helper/README.md.
try:
    from helper.utils import logger, template_path
except ImportError:
    from utils import logger, template_path

#: Where the generated environment lands. install.py symlinks configuration/lock/ here.
ENVIRONMENT_PATH = os.path.join("~", ".config", "lock", "environment")

#: The lock screen's own PAM service, and where the package that owns it puts the file.
#: Naming a service that has no file in /etc/pam.d makes unlocking *impossible* -- PAM falls
#: through to /etc/pam.d/other, which on Arch denies everything -- so the variable below is
#: set only when the file is actually there. A machine without the package keeps Arch's
#: `system-auth`, which is the behaviour this repository had all along.
PAM_SERVICE = "xsecurelock"
PAM_SERVICE_PATH = "/etc/pam.d/xsecurelock"

#: Where the package that installs it lives, for the message that says how.
PAM_PACKAGE_PATH = "configuration/lock/pam"

#: Settings that are a decision rather than a colour, with the reason attached.
BEHAVIOUR = {
    # A passer-by learns nothing about who or what this machine is.
    "XSECURELOCK_SHOW_USERNAME": "0",
    "XSECURELOCK_SHOW_HOSTNAME": "0",
    "XSECURELOCK_SHOW_DATETIME": "0",
    # Show a cursor that jumps to a random position on each keystroke, so the field gives
    # feedback that a key landed without revealing how many have. This is xsecurelock's own
    # default; it is named here because the alternative -- `asterisks`, which every other
    # password prompt uses -- would put the length of the password on a screen that anyone
    # walking past is free to read.
    #
    # Spelled with the documented option. The previous `XSECURELOCK_PARANOID_PASSWORD=1`
    # selected the same thing but has been dropped from xsecurelock's documentation; the
    # binary still honours it, which is exactly how a setting stops being noticed.
    "XSECURELOCK_PASSWORD_PROMPT": "cursor",
    # Blank the screen a minute in, so a locked machine is not also a lit one.
    "XSECURELOCK_BLANK_TIMEOUT": "60",
    "XSECURELOCK_BLANK_DPMS_STATE": "off",
    # The first keypress wakes the screen rather than being swallowed by the prompt.
    "XSECURELOCK_DISCARD_FIRST_KEYPRESS": "1",
    "XSECURELOCK_SAVER_DELAY_MS": "0",
    # Say when caps lock is on. A wrong password with no explanation is the worst thing a
    # lock screen can do, and this is the usual cause. Pinned rather than left to the
    # default because the line below now depends on it being the only thing on that row.
    "XSECURELOCK_SHOW_LOCKS_AND_LATCHES": "1",
    # ... and do not name the keyboard layout, which shares that row and is the long half of
    # it. xsecurelock clears a fixed-width region before redrawing the row rather than one
    # sized to the text it is replacing, so a string wider than that region leaves its ends
    # behind. Toggling caps lock off left `Key` and `ock` in the warning colour either side
    # of the shorter string, because "Keyboard: English (intl., with AltGr dead keys), Caps
    # Lock" overhangs it at both ends. Without the layout the row reads "Keyboard: Caps
    # Lock", which fits. The layout is also the kind of detail this screen withholds
    # anyway -- and one this machine only has a single value for.
    "XSECURELOCK_SHOW_KEYBOARD_LAYOUT": "0",
}


def lock_environment(configuration: dict[str, Any]) -> dict[str, str]:
    """The variables xsecurelock reads, from the active palette and font."""
    theme = configuration["state"]["theme"]
    palette = configuration["palette"][theme]
    font = configuration["font"]
    return {
        # The screen behind the prompt, and the prompt itself.
        "XSECURELOCK_BACKGROUND_COLOR": palette["background"],
        "XSECURELOCK_AUTH_BACKGROUND_COLOR": palette["background"],
        "XSECURELOCK_AUTH_FOREGROUND_COLOR": palette["foreground"],
        # A wrong password is the one moment the lock screen has something to say.
        "XSECURELOCK_AUTH_WARNING_COLOR": palette["warning"],
        "XSECURELOCK_FONT": f"{font['family']}:size={round(font['size'] * 0.85)}",
        **BEHAVIOUR,
        **pam_service(),
    }


def pam_service() -> dict[str, str]:
    """Point xsecurelock at its own PAM stack, if one is installed.

    Arch compiles xsecurelock with ``--with-pam-service-name=system-auth``, and Arch's
    system-auth answers a wrong password with no message -- pam_unix fails silently and
    pam_faillock's ``authfail`` dies at once -- so the screen had nothing to draw and showed
    an empty field. ``configuration/lock/pam/`` packages a stack that says so.

    Conditional, and deliberately so. This is the one setting here that can make the screen
    impossible to unlock rather than merely uninformative, and the failure is silent until
    somebody is locked out in front of it.
    """
    if not os.path.exists(PAM_SERVICE_PATH):
        logger.info(
            f"No {PAM_SERVICE_PATH}; the lock screen will use Arch's system-auth and stay "
            f"silent on a wrong password. Install it with: "
            f"cd {PAM_PACKAGE_PATH} && makepkg --syncdeps --install"
        )
        return {}
    return {"XSECURELOCK_PAM_SERVICE": PAM_SERVICE}


def patch_lock(configuration: dict[str, Any]) -> None:
    path = os.path.expanduser(ENVIRONMENT_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write("# Generated by helper/patch_lock.py — edits are overwritten.\n")
        for name, value in lock_environment(configuration).items():
            handle.write(f'{name}="{value}"\n')
            handle.write(f"export {name}\n")
    logger.info("Patched lock configuration ...")


def install_pam_service() -> bool:
    """Build and install the package that owns ``/etc/pam.d/xsecurelock``.

    A package rather than a copy, because this file decides whether a screen unlocks: pacman
    then names its owner, removes it cleanly, and leaves a ``.pacnew`` rather than replacing a
    stack somebody edited. The two patchers that install into root-owned directories copy with
    ``root_prefix``; nothing there could have offered any of that.

    ``makepkg`` is run rather than ``sudo makepkg``: it refuses to run as root and calls pacman
    for the install step itself, which is where the prompt belongs.
    """
    directory = template_path("lock", "pam")
    if not os.path.isfile(os.path.join(directory, "PKGBUILD")):
        logger.warning(f"No PKGBUILD in {directory}; nothing to install.")
        return False
    try:
        result = subprocess.run(
            ["makepkg", "--syncdeps", "--install", "--needed", "--noconfirm"],
            cwd=directory, check=False,
        )
    except OSError as error:
        logger.warning(f"Could not run makepkg: {error}")
        return False
    if result.returncode != 0:
        logger.warning(f"makepkg exited {result.returncode}; the PAM service is not installed.")
        return False

    logger.info(f"Installed {PAM_SERVICE_PATH}.")
    logger.info(
        "Re-run this patcher to point the lock screen at it, then verify once before "
        "relying on it: lock the screen, type a wrong password, and check that it says so. "
        "If a correct password is ever refused, switch to another terminal with Ctrl-Alt-F1 "
        "and run `killall xsecurelock`."
    )
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--configuration", default="~/.config/config.json", dest="configuration_file_path",
        help="path to the active configuration (default: ~/.config/config.json)",
    )
    parser.add_argument(
        "--install-pam", action="store_true",
        help=f"build and install the package owning {PAM_SERVICE_PATH}, so a wrong password "
             "says so instead of showing an empty field",
    )
    arguments = parser.parse_args(argv)

    if arguments.install_pam and not install_pam_service():
        return 1

    with open(os.path.expanduser(arguments.configuration_file_path)) as input_handle:
        patch_lock(json.load(input_handle))
    return 0


if __name__ == "__main__":
    sys.exit(main())
