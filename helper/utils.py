"""Common helpers shared by ``install.py`` and the patchers.

Exports the install helpers -- ``install_file``, ``install_folder``, ``install_files``,
``install_folders``, ``install_credentials`` -- plus ``monitor_average`` for the patchers
that scale to the display, and the ``logger`` every one of them reports through. Each
install helper logs a one-line status via loguru, or stdlib logging if loguru is absent.

Nothing here copies. Every install path ends in ``os.symlink``, so an installed file *is*
the repository file -- which is what lets a theme switch and a hand edit under
``~/.config`` both land in the tree, and why anything written into an installed path
lands on a tracked file.
"""

import json
import os
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
    permitted, pkexec puts the dialog on the desktop and sudo on the terminal.
    """
    if os.geteuid() == 0:
        return []
    if shutil.which("sudo") and subprocess.run(
        ["sudo", "-n", "true"], capture_output=True, check=False
    ).returncode == 0:
        return ["sudo", "-n"]
    if not prompt:
        return None
    if os.environ.get("DISPLAY") and shutil.which("pkexec"):
        return ["pkexec"]
    if sys.stdin.isatty() and shutil.which("sudo"):
        return ["sudo"]
    return None


def template_path(app: str, filename: str) -> str:
    """The tracked source a patcher reads for an app whose output lands on a tracked path.

    ``~/.config/<app>`` is a symlink into this repository, so a patcher that read and rewrote
    its own target would rewrite a tracked file on every theme switch. Reading a template and
    writing the output beside it keeps the source in version control and the output out of
    it, which is what .gitignore covers.
    """
    return os.path.join(REPOSITORY_ROOT, "configuration", app, filename)


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


def install_folders(folders_paths: dict[str, str], name: str | None = None) -> None:
    logger.info(f"Installing {name if name is not None else 'folders'}...")
    for source_folder_path, destination_folder_path in folders_paths.items():
        install_folder(source_folder_path, destination_folder_path, name)


def install_files(files_paths: dict[str, str], name: str | None = None) -> None:
    logger.info(f"Installing {name if name is not None else 'files'}...")
    for source_file_path, destination_file_path in files_paths.items():
        install_file(source_file_path, destination_file_path, name)


def install_file(source_path: str, destination_path: str, name: str | None = None) -> None:
    source_path = os.path.expanduser(source_path)
    destination_path = os.path.expanduser(destination_path)
    # check if file exists
    if os.path.exists(destination_path) or os.path.islink(destination_path):
        logger.info(f"File {destination_path} already exists.")
        # check if it is a symlink
        if os.path.islink(destination_path):
            logger.info(f"File {destination_path} is already linked.")
            os.unlink(destination_path)
            os.symlink(source_path, destination_path)
        else:
            logger.info(f"Backing up existing file {destination_path}.")
            timestamp = int(time.time())
            os.rename(
                destination_path,
                f"{destination_path}.{timestamp}.bak",
            )
            logger.info(
                f"Backed up existing file to {destination_path}.{timestamp}.bak."
            )
            logger.info(f"Linking {source_path} to {destination_path}.")
            os.symlink(source_path, destination_path)
    else:
        # check if parent folder exists
        parent_destination_folder = os.path.dirname(destination_path)
        if not os.path.exists(parent_destination_folder):
            logger.info(f"Creating parent folder {parent_destination_folder}.")
            os.makedirs(parent_destination_folder, exist_ok=True)
        logger.info(f"Linking {source_path} to {destination_path}.")
        os.symlink(source_path, destination_path)
    if name is not None:
        logger.info(f"Installed {name} configuration.")


def install_folder(source_path: str, destination_path: str, name: str | None = None) -> None:
    source_path = os.path.expanduser(source_path)
    destination_path = os.path.expanduser(destination_path)
    # check if folder exists
    if os.path.exists(destination_path):
        logger.info(f"Folder {destination_path} already exists.")
        # check if it is a symlink
        if os.path.islink(destination_path):
            logger.info(f"Folder {destination_path} is already linked.")
            os.unlink(destination_path)
            os.symlink(source_path, destination_path, target_is_directory=True)
        else:
            logger.info(f"Backing up existing folder {destination_path}.")
            timestamp = int(time.time())
            os.rename(
                destination_path,
                f"{destination_path}.{timestamp}.bak",
            )
            logger.info(
                f"Backed up existing folder to {destination_path}.{timestamp}.bak."
            )
            logger.info(f"Linking {source_path} to {destination_path}.")
            os.symlink(source_path, destination_path, target_is_directory=True)
    else:
        # check if parent folder exists
        parent_destination_folder = os.path.dirname(destination_path)
        if not os.path.exists(parent_destination_folder):
            logger.info(f"Creating parent folder {parent_destination_folder}.")
            os.makedirs(parent_destination_folder, exist_ok=True)
        logger.info(f"Linking {source_path} to {destination_path}.")
        os.symlink(source_path, destination_path, target_is_directory=True)
    if name is not None:
        logger.info(f"Installed {name} configuration.")


def install_credentials(
    credentials: list[str],
    destination_path: str | None = None,
) -> None:
    if destination_path is None:
        destination_path = os.path.join("~", ".config", "credentials.json")
    secrets = {}
    logger.info("Installing credentials...")
    for credential in credentials:
        secret = input(f"Enter the value for {credential}: ")
        secrets[credential] = secret
    destination_path = os.path.expanduser(destination_path)
    if os.path.exists(destination_path):
        logger.info(f"Credentials file {destination_path} already exists.")
        timestamp = int(time.time())
        os.rename(
            destination_path,
            f"{destination_path}.{timestamp}.bak",
        )
        # change file permissions of the backup file to read only for the user
        os.chmod(f"{destination_path}.{timestamp}.bak", 0o600)
        logger.info(
            f"Backed up existing credentials file to {destination_path}.{timestamp}.bak."
        )
    # Create with 0600 already set rather than chmod'ing afterwards: the previous order
    # left the API token on disk world-readable for the window between write and chmod.
    descriptor = os.open(destination_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(secrets, handle, indent=4)
    logger.info(f"Installed credentials to {destination_path}.")


if __name__ == "__main__":
    pass
