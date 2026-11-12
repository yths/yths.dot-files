"""Atomic access to ``~/.config/config.json`` for the qtile bar cells.

Three cells persist state into the shared configuration file: the day/night theme, the
urgent-wallpaper condition, and the audio device mode. They run on qtile's event loop, so
they cannot interleave with each other — but the patchers under ``helper/`` and
``install.py`` are separate processes that read the same file. A plain ``open(path, "w")``
truncates before it refills, so a reader landing in that window sees a partial file. Writing
a sibling temporary and renaming it over the target closes that window: ``os.replace`` is
atomic on POSIX, so a reader observes either the old file or the new one.
"""

import contextlib
import json
import os
import tempfile
from typing import Any

CONFIGURATION_FILE_PATH = os.path.expanduser(os.path.join("~", ".config", "config.json"))


def read_state(configuration_file_path: str = CONFIGURATION_FILE_PATH) -> dict[str, Any]:
    """Return the parsed configuration, or an empty dict if it is missing or malformed."""
    try:
        with open(configuration_file_path, encoding="utf-8") as handle:
            configuration = json.load(handle)
    except (OSError, ValueError):
        return {}
    return configuration if isinstance(configuration, dict) else {}


def write_state(
    configuration: dict[str, Any],
    configuration_file_path: str = CONFIGURATION_FILE_PATH,
) -> bool:
    """Replace the configuration file atomically. Returns whether the write landed."""
    directory = os.path.dirname(configuration_file_path) or "."
    # mkstemp rather than NamedTemporaryFile: the file has to outlive the handle so it can
    # be renamed into place, and it must land in the same directory for os.replace to be
    # an atomic rename rather than a cross-filesystem copy.
    descriptor, temporary_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(configuration, handle, indent=4)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, configuration_file_path)
    except (OSError, ValueError, TypeError):
        with contextlib.suppress(OSError):
            os.unlink(temporary_path)
        return False
    return True


def update_state(
    configuration_file_path: str = CONFIGURATION_FILE_PATH, **changes: Any
) -> dict[str, Any]:
    """Merge ``changes`` into the ``state`` block and write it back atomically.

    Returns the configuration as written, so callers can read neighbouring keys without a
    second round trip.
    """
    configuration = read_state(configuration_file_path)
    if not configuration:
        return configuration
    configuration.setdefault("state", {}).update(changes)
    write_state(configuration, configuration_file_path)
    return configuration
