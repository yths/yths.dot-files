"""Give a connected bluetooth device its icon in the bar, picked from a previewed list.

The bar draws every connected device as ``bluetooth.device`` unless the theme's
``bluetooth_devices`` block maps its MAC to something else, and writing that block by hand
means looking up an address and a Nerd Font codepoint. This asks BlueZ what is connected,
lists the common device glyphs with the bar as each one would leave it, and writes the choice
to both places that hold the mapping: the active bundle's ``config.json``, which a migration
re-derives from, and ``~/.config/config.json``, which the bar reads.

Usage::

    python helper/bluetooth_icon.py                      # pick a device, then its icon
    python helper/bluetooth_icon.py --list               # connected devices and their icons
    python helper/bluetooth_icon.py --symbol mouse       # no menu; the one connected device
    python helper/bluetooth_icon.py --address AA:BB:CC:DD:EE:FF --symbol default

At the icon prompt a number or a name picks from the list, and anything else is taken as the
glyph itself, so an icon the list lacks can be pasted in.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any

import list_themes
import symbols as vocabulary

#: The choice that removes a device's entry, so it is drawn as ``bluetooth.device`` again.
DEFAULT = "default"

#: The common device icons, by the name typed at the prompt. A value naming a symbol key
#: resolves through the vocabulary and so follows the theme; the rest are Material Design
#: glyphs from the Nerd Font private-use plane, stored as written.
COMMON: dict[str, str] = {
    "headphones": "bluetooth.headphones",
    "earbuds": "\U000f184f",
    "speaker": "\U000f04c3",
    "speaker-bluetooth": "\U000f09a2",
    "microphone": "\U000f036c",
    "mouse": "\U000f037d",
    "trackpad": "\U000f07f8",
    "keyboard": "\U000f030c",
    "gamepad": "\U000f0297",
    "pen": "\U000f03ea",
    "phone": "\U000f011c",
    "tablet": "\U000f04f6",
    "laptop": "\U000f0322",
    "watch": "\U000f0589",
    "television": "\U000f0502",
    "remote": "\U000f0454",
    "camera": "\U000f0100",
    "printer": "\U000f042a",
    "car": "\U000f010b",
}

#: What BlueZ calls a device's class, to the entry above offered as the default answer.
SUGGESTIONS = {
    "audio-headset": "headphones",
    "audio-headphones": "headphones",
    "audio-card": "speaker",
    "input-mouse": "mouse",
    "input-keyboard": "keyboard",
    "input-gaming": "gamepad",
    "input-tablet": "pen",
    "phone": "phone",
    "computer": "laptop",
    "video-display": "television",
    "camera-photo": "camera",
    "camera-video": "camera",
    "printer": "printer",
}

_DEVICE_LINE = re.compile(r"^Device\s+((?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})\s*(.*)$")
_ADDRESS = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def installed_path() -> str:
    return os.path.expanduser(os.path.join("~", ".config", "config.json"))


def parse_devices(output: str) -> dict[str, str]:
    """``bluetoothctl devices`` output as upper-case MAC -> name, in the order reported."""
    devices = {}
    for line in output.splitlines():
        match = _DEVICE_LINE.match(line.strip())
        if match:
            devices[match.group(1).upper()] = match.group(2).strip() or match.group(1).upper()
    return devices


def _bluetoothctl(*arguments: str) -> str:
    try:
        return subprocess.run(
            ["bluetoothctl", *arguments], capture_output=True, text=True, timeout=10, check=False
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def connected_devices() -> dict[str, str]:
    return parse_devices(_bluetoothctl("devices", "Connected"))


def suggestion(address: str) -> str | None:
    """The list entry BlueZ's class for this device points at, if it reports one."""
    match = re.search(r"^\s*Icon:\s*(\S+)", _bluetoothctl("info", address), re.MULTILINE)
    return SUGGESTIONS.get(match.group(1)) if match else None


def set_mapping(configuration: dict[str, Any], address: str, value: str | None) -> None:
    """Map ``address`` to ``value`` in ``configuration``, or unmap it when ``value`` is None.

    Replaces an entry for the same address in any case, so a hand-typed lower-case MAC does
    not end up beside its upper-case twin with the winner decided by dict order.
    """
    mapping = {
        key: icon
        for key, icon in (configuration.get("bluetooth_devices") or {}).items()
        if key.upper() != address.upper()
    }
    if value is not None:
        mapping[address.upper()] = value
    configuration["bluetooth_devices"] = mapping


def resolve_choice(answer: str) -> str | None:
    """A prompt answer as the value to store: None to unmap, a symbol key, or a glyph.

    Raises ``ValueError`` for a number outside the list.
    """
    answer = answer.strip()
    names = [DEFAULT, *COMMON]
    if answer.isdigit():
        if int(answer) >= len(names):
            raise ValueError(f"there is no entry {answer}")
        answer = names[int(answer)]
    if answer == DEFAULT:
        return None
    return COMMON.get(answer, answer)


def bar(configuration: dict[str, Any], devices: dict[str, str]) -> str:
    """The icons the bar draws for ``devices`` under ``configuration``, without batteries."""
    active, _ = vocabulary.resolve(configuration)
    mapped = vocabulary.bluetooth_devices(configuration, active)
    return " ".join(mapped.get(address, active["bluetooth.device"]) for address in devices)


def _with(configuration: dict[str, Any], address: str, value: str | None) -> dict[str, Any]:
    candidate = dict(configuration)
    set_mapping(candidate, address, value)
    return candidate


def print_menu(configuration: dict[str, Any], devices: dict[str, str], address: str) -> None:
    """Every choice, with its own glyph and the bar as it would look with it applied."""
    shown = devices if address in devices else {**devices, address: address}
    width = max(len(name) for name in (DEFAULT, *COMMON))
    for index, name in enumerate((DEFAULT, *COMMON)):
        candidate = _with(configuration, address, resolve_choice(name))
        glyph = bar(candidate, {address: ""})
        print(f"  {index:>2}  {glyph}  {name:<{width}}   bar: {bar(candidate, shown)}")


def choose_device(configuration: dict[str, Any], devices: dict[str, str]) -> str | None:
    if not devices:
        print("no bluetooth device is connected; pass --address to map one anyway", file=sys.stderr)
        return None
    addresses = list(devices)
    if len(addresses) == 1:
        return addresses[0]
    for index, address in enumerate(addresses, start=1):
        print(f"  {index:>2}  {bar(configuration, {address: ''})}  {devices[address]}  ({address})")
    answer = input("device: ").strip()
    if answer.isdigit() and 1 <= int(answer) <= len(addresses):
        return addresses[int(answer) - 1]
    print(f"there is no device {answer!r}", file=sys.stderr)
    return None


def choose_symbol(
    configuration: dict[str, Any], devices: dict[str, str], address: str
) -> tuple[bool, str | None]:
    """Ask for the icon. Returns whether one was chosen, and the value to store."""
    print_menu(configuration, devices, address)
    suggested = suggestion(address)
    prompt = f"icon [{suggested}]: " if suggested else "icon: "
    answer = input(prompt).strip() or suggested
    if not answer:
        return False, None
    try:
        return True, resolve_choice(answer)
    except ValueError as error:
        print(error, file=sys.stderr)
        return False, None


def _rewrite(path: str, address: str, value: str | None, trailing_newline: bool) -> None:
    with open(path, encoding="utf-8") as handle:
        configuration = json.load(handle)
    set_mapping(configuration, address, value)
    temporary = f"{path}.tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(configuration, handle, indent=4)
        if trailing_newline:
            handle.write("\n")
    os.replace(temporary, path)


def write(configuration: dict[str, Any], address: str, value: str | None) -> list[str]:
    """Store the mapping in the installed configuration and its bundle; the paths written."""
    written = []
    bundle = os.path.join(
        list_themes.assets_folder(), str(configuration.get("name", "")), "config.json"
    )
    if os.path.isfile(bundle):
        _rewrite(bundle, address, value, trailing_newline=True)
        written.append(bundle)
    else:
        print(f"no bundle at {bundle}; the next migration will drop this", file=sys.stderr)
    _rewrite(installed_path(), address, value, trailing_newline=False)
    written.append(installed_path())
    return written


def reload_bar() -> None:
    """Have qtile reread its configuration; the widget takes the mapping when it is built."""
    try:
        subprocess.run(
            ["qtile", "cmd-obj", "-o", "cmd", "-f", "reload_config"],
            capture_output=True, timeout=30, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        print("qtile was not reloaded; reload it to see the new icon", file=sys.stderr)


def list_devices(configuration: dict[str, Any], devices: dict[str, str]) -> int:
    for address, name in devices.items():
        print(f"{bar(configuration, {address: ''})}  {name}  ({address})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true", help="print connected devices and exit")
    parser.add_argument("--address", help="the device's MAC; asked for when several are connected")
    parser.add_argument(
        "--symbol", help=f"a name from the list, '{DEFAULT}' to unmap, or the glyph itself"
    )
    parser.add_argument("--no-reload", action="store_true", help="leave qtile as it is")
    arguments = parser.parse_args(argv)

    with open(installed_path(), encoding="utf-8") as handle:
        configuration = json.load(handle)
    devices = connected_devices()
    if arguments.list:
        return list_devices(configuration, devices)

    if arguments.address and not _ADDRESS.match(arguments.address):
        print(f"{arguments.address!r} is not a MAC address", file=sys.stderr)
        return 1
    try:
        address = (arguments.address or choose_device(configuration, devices) or "").upper()
        if not address:
            return 1
        if arguments.symbol:
            value = resolve_choice(arguments.symbol)
        else:
            chosen, value = choose_symbol(configuration, devices, address)
            if not chosen:
                return 1
    except (EOFError, KeyboardInterrupt):
        print()
        return 1
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1

    for path in write(configuration, address, value):
        print(f"wrote {path}")
    shown = devices if address in devices else {**devices, address: address}
    print(f"bar: {bar(_with(configuration, address, value), shown)}")
    if not arguments.no_reload:
        reload_bar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
