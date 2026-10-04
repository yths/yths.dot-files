"""The symbols and strings every surface draws, in ASCII, for a theme to override.

The palette made colour a theme's decision; this does the same for the two other things a
surface displays. Every value here is **ASCII**, so the desktop stays readable on a machine
whose font has no private-use area -- which is the state a fresh install is in, and the one
`setup.toml` warns about rather than handles ("It must be a Nerd Font -- the bar draws glyphs
from the private use area"). Nothing in this repository asks whether a glyph is renderable,
so the fallback cannot be conditional on that; it has to be the default, with the glyphs
layered on top by whoever knows the font is there.

A theme bundle overrides what it cares about, through `symbols` and `strings` blocks in its
`config.json`. `install.py` merges them over these defaults, so a bundle that carries neither
gets a working ASCII desktop and a bundle that carries both gets exactly what it asked for.
The tracked `assets/default/` bundle carries this repository's own glyphs, which is why
nothing changes visually on a machine that already has the font.

Two shapes of value:

- a **string**, for a single icon or a message;
- a **tuple**, for a ramp -- a ladder indexed by a level, like the battery's eleven steps or
  the audio meter's eight. `RAMP_LENGTHS` records how long each one has to be, because a
  short ramp is an `IndexError` in a widget rather than a visibly wrong glyph.

Spacing is deliberately *not* here. Several glyphs need a trailing space because their ink
overruns the advance width, which is a property of the glyph and its renderer rather than of
the vocabulary -- so the consumer adds it, and an ASCII fallback is not stuck with padding it
does not need.
"""

from typing import Any

# Resolves whether this runs as ``helper.symbols`` or as a script; see helper/README.md.
try:
    from helper.utils import merge_overrides
except ImportError:
    from utils import merge_overrides

#: How many rungs each ramp has. A consumer indexes these by a level it computed, so a ramp
#: of the wrong length fails as an IndexError at draw time -- in qtile's case inside a
#: ``poll()``, which takes the whole cell down.
RAMP_LENGTHS: dict[str, int] = {
    "battery.discharging": 11,
    "battery.charging": 11,
    "meter.ramp": 8,
}

#: Eight rungs of ascending visual weight, for anything that draws a level as a bar.
_METER_RAMP = (".", ":", "-", "=", "+", "*", "#", "@")

#: Eleven rungs, indexed by ``capacity // 10``. Charging and discharging share the ASCII
#: ladder: with no font to draw two different battery outlines, the two are told apart by
#: ``battery.grid`` being present, which is how the widget already signals AC. A theme that
#: has the glyphs overrides them separately.
_BATTERY_RAMP = ("_", "_", ".", ":", "-", "=", "+", "*", "#", "%", "@")

SYMBOLS: dict[str, str | tuple[str, ...]] = {
    # --- the bar's own furniture
    "bar.monitor": "[]",
    "bar.group": "#",
    # --- levels drawn as a ladder
    "meter.ramp": _METER_RAMP,
    "meter.silence": " ",
    "battery.discharging": _BATTERY_RAMP,
    "battery.charging": _BATTERY_RAMP,
    "battery.grid": "AC",
    # --- per-widget icons
    "bluetooth.device": "bt",
    "bluetooth.headphones": "hp",
    "broadcast.on": "rec",
    "broadcast.off": "off",
    "claude.icon": "AI",
    "claude.dead": "--",
    "location.sunrise": "^",
    "location.sunset": "v",
    "location.manual": "=",
    "service.down": "zzz",
    "service.tick": ".",
    "updates.available": "upd",
    "vpn.on": "vpn",
    "vpn.off": "!vpn",
    # --- shared by dunst and the login screen: the prefix before a notification's summary
    "notification.prefix": ">",
    # --- the launcher's mode prompts
    "rofi.run": ">",
    "rofi.window": "#",
    "rofi.power": "!",
    # --- the shell prompt. Only the four characters the prompt itself draws: starship's
    # forty-three distro logos and its per-language icons stay in starship.toml.template,
    # which is already the file you edit to change them.
    "starship.prompt": ">",
    "starship.read_only": "!",
    "starship.git_branch": "br",
    # --- the boot splash. Single characters, because each is rendered into a PNG whose
    # surface is sized for one glyph; a longer string is drawn past the edge and clipped.
    "plymouth.capslock": "A",
    "plymouth.bullet": "*",
    "plymouth.throbber": "o",
    "plymouth.keyboard": "=",
    "plymouth.lock": "#",
    # --- the login screen. Merged *under* each greeter theme's own `symbols`, so a greeter
    # theme still has the last word; see helper/patch_web_greeter.py.
    "greeter.monitor": "[]",
    "greeter.password_prompt": "#",
    "greeter.submit": ">",
    "greeter.shutdown": "off",
    "greeter.restart": "re",
    "greeter.suspend": "zzz",
    "greeter.hibernate": "hib",
    "greeter.brightness": "*",
    "greeter.battery_charging": "+",
    "greeter.battery_discharging": "=",
    "greeter.updates": "upd",
    "greeter.vpn_on": "vpn",
    "greeter.vpn_off": "!vpn",
    "greeter.summary_prefix": ">",
    "greeter.user_prompt": "u",
    "greeter.session_prefix": "#",
    "greeter.session_chevron": "v",
    "greeter.user_list_prefix": "uu",
}

STRINGS: dict[str, str] = {
    # --- the boot splash, one title and one subtitle per mode plymouth can be in. These are
    # the only prose in the tracked configuration, and until now the only part of the splash
    # a theme could not touch: patch_plymouth rewrote its fonts and colours and left the
    # words in the checked-in INI.
    "plymouth.boot.title": "Starting System ...",
    "plymouth.boot.subtitle": (
        "Keep your face always towards the sunshine, and shadow will fall behind you."
    ),
    "plymouth.shutdown.title": "Stopping System...",
    "plymouth.shutdown.subtitle": (
        "Learn as if you will live forever, live like you will die tomorrow."
    ),
    "plymouth.reboot.title": "Restarting System...",
    "plymouth.reboot.subtitle": "Nature does not hurry, yet everything is accomplished.",
    "plymouth.updates.title": "Installing Updates...",
    "plymouth.updates.subtitle": "Do not turn off your computer!",
    "plymouth.system_upgrade.title": "Upgrading System...",
    "plymouth.system_upgrade.subtitle": "Do not turn off your computer!",
    "plymouth.firmware_upgrade.title": "Upgrading Firmware...",
    "plymouth.firmware_upgrade.subtitle": "Do not turn off your computer!",
    "plymouth.system_reset.title": "Restarting System...",
    "plymouth.system_reset.subtitle": "If you are going through hell, keep going.",
    # --- the login screen
    "greeter.welcome": "username",
    "greeter.session": "session",
    "greeter.auth_failed": "authentication failed",
    "greeter.shutdown_title": "shutdown",
    "greeter.restart_title": "restart",
    "greeter.suspend_title": "suspend",
    "greeter.hibernate_title": "hibernate",
    # --- the bar's one widget with words rather than a number
    "claude.no_data": "no data",
    "claude.unavailable": "unavailable",
    "claude.session": "session",
    "claude.weekly": "weekly",
    "claude.stale": "stale",
    "claude.notification_title": "Claude usage",
    # --- tmux's one message
    "tmux.reload": "::: tmux config reloaded :::",
}

#: Which section of plymouth's INI each string pair belongs to. The INI's section names are
#: plymouth's, not ours, and two of them are not valid Python identifiers -- so the mapping
#: is written once here rather than guessed from the key.
PLYMOUTH_SECTIONS: dict[str, str] = {
    "boot-up": "boot",
    "shutdown": "shutdown",
    "reboot": "reboot",
    "updates": "updates",
    "system-upgrade": "system_upgrade",
    "firmware-upgrade": "firmware_upgrade",
    "system-reset": "system_reset",
}


def _ramps(values: dict[str, Any]) -> dict[str, Any]:
    """Tuples for the ramps, whatever JSON handed back.

    A bundle's overrides arrive as lists, and a list is mutable -- a widget that sliced or
    sorted one in place would change the vocabulary for every later caller in the process.
    """
    return {
        key: tuple(value) if isinstance(value, list) else value
        for key, value in values.items()
    }


def resolve(configuration: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """The active vocabulary: these defaults with the configuration's overrides on top.

    Defensive on purpose. A ``~/.config/config.json`` written before this existed carries
    neither block, and the desktop it configures still has to start -- the same reason
    ``configuration/qtile/shared/state.py`` normalises state it reads rather than trusting it.
    """
    symbols = merge_overrides(SYMBOLS, _ramps(configuration.get("symbols") or {}))
    strings = merge_overrides(STRINGS, configuration.get("strings") or {})
    return symbols, strings


def bluetooth_devices(configuration: dict[str, Any], symbols: dict[str, Any]) -> dict[str, str]:
    """The glyph a theme gives particular bluetooth devices, keyed by upper-case MAC.

    Read from the configuration's ``bluetooth_devices`` block. A value naming a symbol key --
    ``"bluetooth.headphones"`` -- resolves through the vocabulary, so it keeps its ASCII
    fallback and follows the bundle's override of that key; anything else is drawn as
    written. A device absent from the block is drawn as ``bluetooth.device``. Keys are
    upper-cased because BlueZ reports addresses that way and a hand-typed MAC need not be.
    """
    resolved = {}
    for address, value in (configuration.get("bluetooth_devices") or {}).items():
        if not isinstance(value, str):
            continue
        glyph = symbols.get(value, value)
        resolved[address.upper()] = glyph if isinstance(glyph, str) else value
    return resolved


def undeclared(configuration: dict[str, Any]) -> list[str]:
    """Override keys that no default declares, newest rot first.

    An override of a key nothing reads is silent: the bundle looks like it set something and
    no surface changes. ``helper/gendocs.py`` refuses a commit while this is non-empty.
    """
    return sorted(
        [key for key in configuration.get("symbols") or {} if key not in SYMBOLS]
        + [key for key in configuration.get("strings") or {} if key not in STRINGS]
    )


def malformed(values: dict[str, Any]) -> list[str]:
    """Ramps of the wrong length, which are an IndexError at draw time rather than a glyph."""
    return sorted(
        f"{key}: {len(values[key])} rungs, expected {expected}"
        for key, expected in RAMP_LENGTHS.items()
        if key in values and len(values[key]) != expected
    )
