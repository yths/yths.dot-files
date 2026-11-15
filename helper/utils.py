"""Common helpers shared by ``install.py`` and the patchers.

Exports the install helpers -- ``install_link`` and ``install_credentials`` -- plus
``monitor_average`` for the patchers that scale to the display, and the ``logger`` every one
of them reports through. Each install helper logs a one-line status via loguru, or stdlib logging if loguru is absent.

Nothing here copies. Every install path ends in ``os.symlink``, so an installed file *is*
the repository file -- which is what lets a theme switch and a hand edit under
``~/.config`` both land in the tree, and why anything written into an installed path
lands on a tracked file.
"""

import getpass
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
from typing import Any

try:
    import loguru
    logger = loguru.logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


#: This repository, resolved through any symlink used to invoke a helper.
REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

#: The one file a reader edits to adopt this repository: theme, font, initial state,
#: credentials to prompt for, and the packages to install.
SETUP_PATH = os.path.join(REPOSITORY_ROOT, "setup.toml")


def read_setup(path: str | None = None) -> dict[str, Any]:
    """Parse ``setup.toml``.

    Read rather than imported so the values live in one editable file instead of as constants
    spread through the installer, the bootstrap script and the documentation. ``tomllib`` is
    in the standard library, so this costs no dependency.
    """
    with open(path or SETUP_PATH, "rb") as handle:
        return tomllib.load(handle)


def root_prefix(*, prompt: bool) -> list[str] | None:
    """An argv prefix that runs a command as root here, or ``None`` if nothing can.

    An empty list means the caller is already root. ``sudo -n`` is tried first because it
    either works silently — a live timestamp, or a NOPASSWD rule — or fails immediately;
    it is the only form the unattended theme switch is allowed to use. When prompting is
    permitted, a terminal gets sudo and only a terminal-less caller gets pkexec: without a
    graphical polkit agent pkexec falls back to its text agent, which polkit 127's
    socket-activated helper rejects with "No session for cookie" whatever password is typed.
    sudo also asks once for a run that needs root twice.
    """
    if os.geteuid() == 0:
        return []
    if shutil.which("sudo") and subprocess.run(
        ["sudo", "-n", "true"], capture_output=True, check=False
    ).returncode == 0:
        return ["sudo", "-n"]
    if not prompt:
        return None
    if sys.stdin.isatty() and shutil.which("sudo"):
        return ["sudo"]
    if os.environ.get("DISPLAY") and shutil.which("pkexec"):
        return ["pkexec"]
    return None


def authenticate() -> list[str] | None:
    """Ask for root now, so the steps after it can use it without asking. ``None`` if refused.

    With sudo this caches the credentials (``sudo -v``), and every later ``root_prefix`` finds
    them through ``sudo -n``: one prompt, before anything has changed, rather than one in the
    middle of a half-applied switch. pkexec has no such cache and asks at each step.
    """
    prefix = root_prefix(prompt=True)
    if prefix != ["sudo"]:
        return prefix
    if subprocess.run(["sudo", "-v"], check=False).returncode != 0:
        return None
    return ["sudo", "-n"]


#: Left in every theme directory installed under a system path, so a later install may remove
#: it once another has replaced it -- and never removes a directory something else put there,
#: like the themes a greeter package ships beside ours.
INSTALL_MARKER = ".installed-by-dot-files"


def installed_theme_name(configuration: dict[str, Any]) -> str:
    """The active theme's name, as the name of a directory under a system theme path.

    The login screen and the boot splash install under it, so what a machine shows is named
    for the theme it came from rather than for anyone's account.
    """
    name = re.sub(r"[^a-z0-9._-]+", "-", str(configuration.get("name") or "").lower())
    return name.strip("-.") or "dot-files"


def remove_previous_installs(root: str, keep: str, prefix: list[str]) -> list[str]:
    """Remove theme directories under ``root`` that this repository installed, but ``keep``.

    Called only once ``keep`` is installed and active, so nothing is removed that is still in
    use. Only directories carrying ``INSTALL_MARKER`` are candidates. Returns the names removed.
    """
    try:
        entries = os.listdir(root)
    except OSError:
        return []
    removed = []
    for entry in sorted(entries):
        path = os.path.join(root, entry)
        if entry == keep or not os.path.isfile(os.path.join(path, INSTALL_MARKER)):
            continue
        result = subprocess.run([*prefix, "rm", "-rf", path], capture_output=True, check=False)
        if result.returncode == 0:
            removed.append(entry)
    return removed


def mark_installed(directory: str, prefix: list[str]) -> bool:
    """Leave ``INSTALL_MARKER`` in an installed theme directory. Returns whether it did."""
    result = subprocess.run(
        [*prefix, "touch", os.path.join(directory, INSTALL_MARKER)],
        capture_output=True, check=False,
    )
    return result.returncode == 0


def template_path(app: str, filename: str) -> str:
    """The tracked source a patcher reads for an app whose output lands on a tracked path.

    ``~/.config/<app>`` is a symlink into this repository, so a patcher that read and rewrote
    its own target would rewrite a tracked file on every theme switch. Reading a template and
    writing the output beside it keeps the source in version control and the output out of
    it, which is what .gitignore covers.
    """
    return os.path.join(REPOSITORY_ROOT, "configuration", app, filename)


def merge_overrides(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """``base`` with ``overrides`` on top, one level deep, leaving ``base`` untouched.

    The rule a partial override needs: a key the override omits keeps the base's value rather
    than disappearing. ``patch_web_greeter`` has relied on that since it let a login theme pin
    its font size without also having to restate the family, and the symbol and string
    vocabularies need the same thing -- a bundle overriding one glyph must not blank the other
    eighty.
    """
    return {**base, **overrides}


def tracked_bundles() -> list[str]:
    """The theme bundles this repository ships, as directory names.

    Distinct from ``install.discover_themes``, which finds *every* bundle under ``assets/``
    because that is how a personal theme gets installed. ``.gitignore`` carries ``assets/*``
    with ``!assets/default/`` precisely so a personal bundle can sit there uncommitted -- so
    anything that goes into tracked documentation, or that asserts what this repository ships,
    has to ask git rather than the filesystem. Otherwise exporting a theme of your own puts its
    name in a generated document and refuses the commit.
    """
    listing = subprocess.run(
        ["git", "-C", REPOSITORY_ROOT, "ls-files", "assets/*/config.json"],
        capture_output=True, text=True, check=False,
    ).stdout.split()
    return sorted({name.split("/")[1] for name in listing})


def monitor_average(configuration: dict[str, Any], key: str) -> float | None:
    """Mean of ``key`` across the detected monitors, or ``None`` when there are none.

    Three patchers scale something to the display: rofi's width, xorg's DPI, dunst's offset.
    ``None`` rather than a zero or a raise, because with no monitors there is no meaningful
    average and the caller's right move is to leave its app alone -- computing one anyway
    divides by zero, in the middle of a patcher that may already have opened its target for
    writing.
    """
    monitors = configuration.get("monitors") or {}
    values = [monitor[key] for monitor in monitors.values() if key in monitor]
    if not values:
        return None
    return sum(values) / len(values)


def install_link(source_path: str, destination_path: str, name: str | None = None) -> None:
    """Symlink ``destination_path`` to ``source_path``, a file or a directory alike.

    An existing link is replaced -- dangling or not, which is what a link left by a moved
    repository is. Anything else at the destination is renamed to ``<path>.<timestamp>.bak``
    first, so nothing a user had there is lost.
    """
    source_path = os.path.expanduser(source_path)
    destination_path = os.path.expanduser(destination_path)
    if os.path.islink(destination_path):
        logger.info(f"{destination_path} is already linked; relinking.")
        os.unlink(destination_path)
    elif os.path.exists(destination_path):
        backup_path = f"{destination_path}.{int(time.time())}.bak"
        os.rename(destination_path, backup_path)
        logger.info(f"Backed up existing {destination_path} to {backup_path}.")
    else:
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
    logger.info(f"Linking {source_path} to {destination_path}.")
    os.symlink(source_path, destination_path, target_is_directory=os.path.isdir(source_path))
    if name is not None:
        logger.info(f"Installed {name} configuration.")


CREDENTIALS_PATH = os.path.join("~", ".config", "credentials.json")


def read_credentials(path: str | None = None) -> dict[str, Any]:
    """The credentials file as a dict; empty when it is absent or is not a JSON object."""
    try:
        with open(os.path.expanduser(path or CREDENTIALS_PATH), encoding="utf-8") as handle:
            credentials = json.load(handle)
    except (OSError, ValueError):
        return {}
    return credentials if isinstance(credentials, dict) else {}


def missing_credentials(credentials: list[str], path: str | None = None) -> list[str]:
    """The names in ``credentials`` that the credentials file does not hold yet."""
    present = read_credentials(path)
    return [name for name in credentials if name not in present]


def install_credentials(
    credentials: list[str],
    destination_path: str | None = None,
) -> None:
    """Prompt for each of ``credentials`` and merge them into the credentials file.

    Merged, not written afresh: the file is shared with yths.backend-service, whose
    installer stores keys this one never asks for (``OBS_PASSWORD``), and rewriting it with
    only the names asked for here dropped those.
    """
    destination_path = os.path.expanduser(destination_path or CREDENTIALS_PATH)
    secrets = read_credentials(destination_path)
    logger.info("Installing credentials...")
    for credential in credentials:
        # getpass rather than input: a token typed at an echoing prompt stays in the
        # terminal's scrollback long after the file holding it is chmod 0600.
        secrets[credential] = getpass.getpass(f"Enter the value for {credential}: ")
    if os.path.exists(destination_path):
        logger.info(f"Credentials file {destination_path} already exists.")
        # One backup is enough to undo a mistyped re-run; every older one is a stale copy
        # of secrets nothing reads, so it goes before the new backup is made.
        for stale in glob.glob(f"{glob.escape(destination_path)}.*.bak"):
            os.remove(stale)
            logger.info(f"Removed older credentials backup {stale}.")
        timestamp = int(time.time())
        backup_path = f"{destination_path}.{timestamp}.bak"
        os.rename(destination_path, backup_path)
        os.chmod(backup_path, 0o600)
        logger.info(f"Backed up existing credentials file to {backup_path}.")
    # Create with 0600 already set rather than chmod'ing afterwards: the previous order
    # left the API token on disk world-readable for the window between write and chmod.
    descriptor = os.open(destination_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(secrets, handle, indent=4)
    logger.info(f"Installed credentials to {destination_path}.")
