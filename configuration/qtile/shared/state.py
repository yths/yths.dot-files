"""Atomic access to ``~/.config/config.json`` for the qtile bar cells.

Three cells persist state into the shared configuration file: the day/night theme, the
urgent-wallpaper condition, and the audio device mode. It also normalises the one state
key and one value that predate the current vocabulary; see ``normalise_state``. They run on qtile's event loop, so
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

#: State keys written before the current vocabulary, mapped onto it. ``mode`` became
#: ``theme_mode`` once ``audio_mode`` existed and the unprefixed name no longer said which
#: mode it meant (7fbbdd5, 2026-08-29).
#:
#: Delete once every machine's ``~/.config/config.json`` has been written since that date.
#: ``install.py`` rebuilds the file from scratch, so one install per machine is enough; the
#: file is not tracked, so no commit here can do it for them. Nothing detects when that is
#: true, which is why the date is recorded rather than the condition being left to memory.
LEGACY_STATE_KEYS = {"mode": "theme_mode"}

#: The two keys that answer "does this follow the system, or did the user pin it".
MODE_KEYS = ("theme_mode", "audio_mode")

#: ``audio_mode`` spelled ``"auto"`` what ``mode`` spelled ``"automatic"``. One spelling now,
#: renamed alongside the keys above and removable on the same condition and date.
LEGACY_MODE_VALUES = {"auto": "automatic"}


def normalise_state(state: dict[str, Any]) -> dict[str, Any]:
    """Return ``state`` in the current vocabulary, translating anything written before it.

    Applied on every read so a configuration file predating the rename keeps working.
    Without it the automatic theme switch would simply stop on any machine that had not been
    reinstalled -- ``state.get("theme_mode")`` would be ``None``, which reads as "the user
    pinned this", and nothing would say so. The first write after a read persists the
    translation, so a file migrates itself at the next theme flip.
    """
    normalised = dict(state)
    for legacy, current in LEGACY_STATE_KEYS.items():
        if legacy in normalised:
            normalised.setdefault(current, normalised[legacy])
            del normalised[legacy]
    for key in MODE_KEYS:
        if normalised.get(key) in LEGACY_MODE_VALUES:
            normalised[key] = LEGACY_MODE_VALUES[normalised[key]]
    return normalised


def read_state(configuration_file_path: str = CONFIGURATION_FILE_PATH) -> dict[str, Any]:
    """Return the parsed configuration, or an empty dict if it is missing or malformed."""
    try:
        with open(configuration_file_path, encoding="utf-8") as handle:
            configuration = json.load(handle)
    except (OSError, ValueError):
        return {}
    if not isinstance(configuration, dict):
        return {}
    state = configuration.get("state")
    if isinstance(state, dict):
        configuration["state"] = normalise_state(state)
    return configuration


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
