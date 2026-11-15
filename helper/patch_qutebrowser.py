"""Patch qutebrowser: every colour the browser draws, mapped from its own stock defaults.

The browser used to theme itself. ``configuration/qutebrowser/config.py`` read
``~/.config/config.json`` at startup and indexed the palette for twenty-eight colours chosen
by hand -- which left seventy-seven of its hundred-and-five colour settings stock: the
completion popup yellow on grey, the hints the stock yellow gradient, caret mode purple.
Naming the remaining seventy-seven by hand is the work this avoids.

Instead the stock defaults are read out of ``template_config.py`` -- the dump
``qutebrowser --config-py`` writes, where every setting appears commented out with the value
qutebrowser would use -- and each one is matched to the palette token nearest it in
CAM16-UCS. The match runs against the dark palette, because qutebrowser's stock chrome is a
dark one and matching a black statusbar against a light palette calls it *foreground*; the
colour written is the active mode's entry for the matched token, which is ``patch_vsc``'s
``reference`` method through the same matcher -- including its second look: a ``.fg``
matched onto the same token as its sibling ``.bg`` is re-picked for contrast, so an inactive
tab's title cannot vanish into the tab drawn under it.

Not everything under ``c.colors`` is a colour. Two gradients, an ``rgba()``, eight ``None``s
meaning "let Qt decide", and eleven enums, booleans and numbers are left exactly as
qutebrowser shipped them; :func:`unmapped` names them, so a value that stops being recognised
shows up as a report line rather than as a colour that quietly stayed stock.

The output is ``~/.config/qutebrowser/theme.py``, which ``config.py`` sources. That directory
is qutebrowser's own -- ``install.py`` symlinks the single file ``config.py`` into it rather
than the whole directory -- so unlike every other patcher's output this one lands outside the
repository and needs no ``.gitignore`` entry.
"""

import argparse
import ast
import json
import os
import re
import sys
from typing import Any

import color_match
from utils import logger, template_path

#: A commented setting in the stock dump. The name allows digits because one setting has one
#: (``qt.workarounds.disable_accelerated_2d_canvas``); dropping them from the class silently
#: skips it, which is the kind of miss that looks like a deliberate exclusion.
SETTING = re.compile(r"^# (c\.colors\.[a-z0-9_.]+) = (.+)$", re.M)

#: Where qutebrowser reads it from, and the name ``config.py`` sources.
THEME_PATH = os.path.join("~", ".config", "qutebrowser", "theme.py")


def stock_defaults(source: str) -> dict[str, Any]:
    """Every ``c.colors.*`` setting in the stock dump, with the value qutebrowser ships.

    The dump carries no ``## Default:`` annotation -- the commented assignment *is* the
    default -- so the value is recovered by evaluating it. Every one of them is a Python
    literal, and a line that is not is skipped rather than guessed at.
    """
    defaults = {}
    for name, raw in SETTING.findall(source):
        try:
            defaults[name] = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            continue
    return defaults


def mapped(value: Any, candidates: list, lookup: list | None = None) -> Any | None:
    """``value`` recoloured, or ``None`` if it is not something to recolour.

    A list is mapped element-wise: ``colors.completion.fg`` is one entry per completion
    column, and replacing the list with a single colour would collapse three columns into one.
    ``lookup`` is passed through to :func:`color_match.replace`: the winner is chosen in
    ``candidates`` but written in ``lookup``'s colours, by label.
    """
    if isinstance(value, list):
        replaced = [mapped(entry, candidates, lookup) for entry in value]
        return replaced if all(entry is not None for entry in replaced) else None
    if color_match.to_rgb(value) is None:
        return None
    return color_match.replace(value, candidates, lookup)


def stock_source() -> str:
    """The dump ``qutebrowser --config-py`` wrote, which carries the defaults."""
    with open(template_path("qutebrowser", "template_config.py")) as handle:
        return handle.read()


def theme_settings(configuration: dict[str, Any], mode: str) -> dict[str, str]:
    """``c.colors.*`` name -> the colour this theme gives it.

    Matching each default against the active palette directly kept the chrome dark in light
    mode: qutebrowser's stock UI is dark -- black statusbar, dark completion popup -- and
    nearest-neighbour preserves lightness, so stock ``black`` landed on the light palette's
    *foreground*. VSCode escapes this by shipping a light template; qutebrowser has only the
    one dump. So this is ``patch_vsc``'s ``reference`` method: each default is matched against
    the **dark** palette, which the stock theme resembles, to decide which *token* it is --
    black is the background, white the foreground -- and the hex written is the active mode's
    entry for that token. In dark mode the two palettes are the same one and nothing changes.
    """
    source = stock_source()
    palette_map = color_match.build_palette_map(configuration["palette"])
    reference = palette_map["dark"]
    lookup = palette_map[mode]
    defaults = stock_defaults(source)
    settings = {}
    for name, value in defaults.items():
        replacement = mapped(value, color_match.filter_candidates(name, reference), lookup)
        if replacement is not None:
            settings[name] = replacement
    return with_legible_text(settings, defaults, lookup)


def with_legible_text(
    settings: dict[str, Any], defaults: dict[str, Any], candidates: list
) -> dict[str, Any]:
    """``settings`` with every ``.fg`` that vanished into its own ``.bg`` re-picked.

    Each colour is matched on its own, so a text colour and the surface under it can land on
    one token: against the light palette, the inactive even tabs' stock ``white`` on
    ``darkgrey`` both became the background grey, which drew their titles invisible. The same
    second look as ``patch_vsc.with_legible_text`` -- qutebrowser names its pairs ``.fg`` and
    ``.bg`` where VSCode says ``Foreground`` and ``Background``: a ``.fg`` that no longer
    reads on its sibling ``.bg`` is re-picked by ``color_match.legible``, starting from the
    colour qutebrowser meant. List values (the completion columns) and pairs whose ``.bg``
    stayed stock (a gradient) are left to the plain match.
    """
    legible = dict(settings)
    for name, value in settings.items():
        if not name.endswith(".fg") or not isinstance(value, str):
            continue
        surface = settings.get(name[: -len(".fg")] + ".bg")
        if not isinstance(surface, str):
            continue
        ratio = color_match.contrast(value, surface)
        if ratio is None or ratio >= color_match.MIN_TEXT_CONTRAST:
            continue
        replacement = color_match.legible(defaults.get(name, value), surface, candidates)
        if replacement is not None:
            legible[name] = replacement
    return legible


def unmapped(source: str) -> dict[str, Any]:
    """The settings deliberately left stock, for the report and for the tests."""
    candidates = [{"label": "x", "hex": "#000000", "cam16": color_match.to_rgb("#000000")}]
    return {
        name: value
        for name, value in stock_defaults(source).items()
        if mapped(value, candidates) is None
    }


def theme_module(configuration: dict[str, Any], mode: str) -> str:
    """The generated ``theme.py``."""
    settings = theme_settings(configuration, mode)
    lines = [
        "# Generated by helper/patch_qutebrowser.py — edits are overwritten.",
        "#",
        "# Every colour below is qutebrowser's own default for that setting, matched against",
        "# the dark palette -- which the stock theme resembles -- to decide which token it is,",
        f"# and written as the active {mode} palette's colour for that token. Settings whose",
        "# default is a gradient, an rgba() or not a colour at all are absent: qutebrowser",
        "# keeps its own.",
        "",
        "c = c  # noqa: F821 pylint: disable=E0602,C0103",
        "",
    ]
    lines += [f"{name} = {value!r}" for name, value in sorted(settings.items())]
    return "\n".join(lines) + "\n"


def patch_qutebrowser(configuration: dict[str, Any]) -> None:
    path = os.path.expanduser(THEME_PATH)
    if not os.path.isdir(os.path.dirname(path)):
        logger.info("qutebrowser has no configuration directory; skipping its theme.")
        return
    mode = configuration["state"]["theme"]
    with open(path, "w") as handle:
        handle.write(theme_module(configuration, mode))
    logger.info("Patched qutebrowser configuration ...")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--configuration", default="~/.config/config.json", dest="configuration_file_path",
        help="path to the active configuration (default: ~/.config/config.json)",
    )
    parser.add_argument(
        "--report-unmapped", action="store_true",
        help="list the stock settings left alone, and why, instead of patching",
    )
    arguments = parser.parse_args(argv)

    if arguments.report_unmapped:
        source = stock_source()
        left = unmapped(source)
        print(f"{len(left)} of {len(stock_defaults(source))} settings are left stock:")
        for name, value in sorted(left.items()):
            print(f"  {name} = {value!r}")
        return 0

    with open(os.path.expanduser(arguments.configuration_file_path)) as handle:
        patch_qutebrowser(json.load(handle))
    return 0


if __name__ == "__main__":
    sys.exit(main())
