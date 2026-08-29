"""Apply, inspect and import display colour profiles.

Reads ``configuration/hardware/icc/displays.json`` — a mapping of hostname to
``{display: profile}`` — and hands each connected display to ``dispwin``. Called from
``~/.xinitrc`` at session start, which is why nothing here is fatal: an uncalibrated
display is a worse picture, never a broken session, so every failure path exits 0.
"""

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys

REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
ICC_SOURCE_DIRECTORY = os.path.join(REPOSITORY_ROOT, "configuration", "hardware", "icc")
DISPLAYS_FILE = os.path.join(ICC_SOURCE_DIRECTORY, "displays.json")
#: Where install.py symlinks the profiles, and what ~/.xinitrc loads them from.
ICC_INSTALLED_DIRECTORY = os.path.expanduser(os.path.join("~", ".config", "icc"))
#: Create this to run uncalibrated without editing anything tracked.
DISABLED_SENTINEL = os.path.join(ICC_INSTALLED_DIRECTORY, "disabled")

#: `dispwin -d ?` prints e.g. "    1 = 'Monitor 1, Output HDMI-1 at 3840, 0, ...'".
DISPLAY_LINE = re.compile(r"^\s*(?P<index>\d+) = '[^,]*, Output (?P<output>[^ ]+) ")
#: A profile name is a bare filesystem-safe token; it becomes "<name>.icc".
CANONICAL_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def canonicalise(name: str) -> str:
    """Lowercase, hyphen-separated, no extension — the one filename shape used here."""
    stem = os.path.basename(name)
    for suffix in (".icc", ".icm"):
        if stem.lower().endswith(suffix):
            stem = stem[: -len(suffix)]
    stem = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()
    return re.sub(r"-{2,}", "-", stem)


def read_displays() -> dict[str, dict[str, str]]:
    try:
        with open(DISPLAYS_FILE, encoding="utf-8") as handle:
            mapping = json.load(handle)
    except (OSError, ValueError):
        return {}
    return mapping if isinstance(mapping, dict) else {}


def detect_displays() -> list[tuple[str, str]]:
    """Return ``(index, output)`` for every display dispwin can see, in its own order."""
    try:
        result = subprocess.run(
            ["dispwin", "-d", "?"], capture_output=True, text=True, check=False
        )
    except OSError:
        return []
    found = []
    for line in (result.stdout + result.stderr).splitlines():
        match = DISPLAY_LINE.match(line)
        if match:
            found.append((match.group("index"), match.group("output")))
    return found


def profile_path(name: str) -> str:
    """Prefer the installed copy, fall back to the repository, so this works pre-install."""
    for directory in (ICC_INSTALLED_DIRECTORY, ICC_SOURCE_DIRECTORY):
        candidate = os.path.join(directory, f"{name}.icc")
        if os.path.isfile(candidate):
            return candidate
    return ""


def resolve(host_map: dict[str, str], displays: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Pair each display index with the profile named for its output, or its index."""
    pairs = []
    for index, output in displays:
        name = host_map.get(output) or host_map.get(index)
        if name:
            pairs.append((index, name))
    return pairs


def skip_reason(host_map: dict[str, str], displays: list[tuple[str, str]]) -> str:
    """Why calibration should be skipped entirely, or "" to go ahead.

    Each of these is a normal state, not an error: no calibration tooling installed, no
    profiles recorded for this machine, no displays, or the user having switched it off.
    """
    if os.path.exists(DISABLED_SENTINEL):
        return f"colour management disabled by {DISABLED_SENTINEL}"
    if shutil.which("dispwin") is None:
        return "dispwin not installed (yay -S displaycal); leaving displays uncalibrated"
    if not host_map:
        return f"no display profiles configured for host {platform.node()!r}"
    if not displays:
        return "dispwin reported no displays"
    return ""


def apply_profiles(verbose: bool) -> int:
    host_map = read_displays().get(platform.node(), {})
    displays = detect_displays() if shutil.which("dispwin") else []

    reason = skip_reason(host_map, displays)
    if reason:
        if verbose:
            print(reason)
        return 0

    for index, name in resolve(host_map, displays):
        path = profile_path(name)
        if not path:
            print(f"profile {name!r} not found; display {index} left uncalibrated")
            continue
        # The profile is passed positionally: dispwin's `calfile` argument loads the
        # calibration into the video LUT, which is what a session start wants. `-I` would
        # additionally register it as the display's system profile, and `-i` -- which the
        # hand-written .xinitrc lines used -- is actually "run forever with random values".
        outcome = subprocess.run(
            ["dispwin", "-d", index, path], capture_output=True, text=True, check=False
        )
        if outcome.returncode == 0:
            if verbose:
                print(f"display {index}: applied {name}")
        else:
            print(f"display {index}: dispwin failed for {name} ({outcome.returncode})")
    return 0


def list_displays() -> int:
    host = platform.node()
    host_map = read_displays().get(host, {})
    displays = detect_displays()
    print(f"host: {host}")
    print(f"disabled: {os.path.exists(DISABLED_SENTINEL)} ({DISABLED_SENTINEL})")
    if not displays:
        print("no displays reported by dispwin")
    for index, output in displays:
        name = host_map.get(output) or host_map.get(index)
        path = profile_path(name) if name else ""
        state = f"{name} -> {path}" if path else (f"{name} (file missing)" if name else "no profile configured")
        print(f"  display {index}  output {output:10} {state}")
    return 0


def import_profile(source: str, display: str, name: str | None) -> int:
    """Copy a freshly calibrated profile into the repository and register it."""
    if not os.path.isfile(source):
        print(f"no such file: {source}", file=sys.stderr)
        return 1
    stem = canonicalise(name or source)
    if not CANONICAL_NAME.match(stem):
        print(f"{stem!r} is not a usable profile name", file=sys.stderr)
        return 1

    destination = os.path.join(ICC_SOURCE_DIRECTORY, f"{stem}.icc")
    existed = os.path.exists(destination)
    shutil.copyfile(source, destination)

    mapping = read_displays()
    mapping.setdefault(platform.node(), {})[display] = stem
    with open(DISPLAYS_FILE, "w", encoding="utf-8") as handle:
        json.dump(mapping, handle, indent=4)
        handle.write("\n")

    verb = "replaced" if existed else "added"
    print(f"{verb} {destination}")
    print(f"registered {platform.node()} / {display} -> {stem}")
    print("commit both to keep the calibration history in git, then re-run install.py")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true", help="show displays and their profiles")
    parser.add_argument("--verbose", action="store_true", help="report what was applied")
    parser.add_argument("--import-profile", metavar="PATH", help="copy a calibrated profile in")
    parser.add_argument("--display", metavar="KEY", help="output name or index it belongs to")
    parser.add_argument("--name", metavar="NAME", help="profile name (default: from the filename)")
    arguments = parser.parse_args()

    if arguments.import_profile:
        if not arguments.display:
            parser.error("--import-profile requires --display")
        return import_profile(arguments.import_profile, arguments.display, arguments.name)
    if arguments.list:
        return list_displays()
    return apply_profiles(arguments.verbose)


if __name__ == "__main__":
    sys.exit(main())
