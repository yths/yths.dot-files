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
meaning "let Qt decide", and eleven enums, booleans and numbers have nothing to be matched
from; :func:`unmapped` names them, so a value that stops being recognised shows up as a
report line rather than as a colour that quietly stayed stock.

Two surfaces are declared rather than matched. The tabs follow the qtile task list
(:func:`tab_settings`), because they are the same thing one level down -- a row of cells, one
of them active -- and matching their stock greys and greens gave a second, unrelated scheme
right under the first. And the hints are declared outright (:func:`hint_settings`), because
their stock background is one of the gradients: left alone it stayed qutebrowser's yellow
while the text over it followed the palette, and in light mode that text was the light
background colour.

One more is declared for a different reason. ``colors.webpage.bg`` is what shows under a page
that sets no background of its own, and such a page sets no text colour either: its text is
black. Matched like the rest, stock ``white`` became the active palette's dark end in light
mode, and those pages were black on near-black (:func:`page_settings`).

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


#: The kinds of tab that are not selected, in the order they move away from the bar's colour.
INACTIVE_TABS = ("even", "odd", "pinned.even", "pinned.odd")

#: The selected tab, in each of the places qutebrowser names it.
ACTIVE_TABS = ("selected.even", "selected.odd", "pinned.selected.even", "pinned.selected.odd")

#: The load stripe's two outcomes, and the palette token that already means each.
INDICATORS = {"stop": "success", "error": "failure"}


def legible_reach(surface: str, toward: str, text: str) -> float:
    """How far ``surface`` can move toward ``toward`` before ``text`` stops reading on it.

    A weight for :func:`color_match.mix`, found by walking the mix in hundredths until the
    contrast drops under body text's. Zero when the text does not read on the surface itself.
    """
    reach = -1
    for step in range(101):
        blended = color_match.mix(surface, toward, step / 100)
        if (color_match.contrast(text, blended) or 0) < color_match.MIN_TEXT_CONTRAST:
            break
        reach = step
    return max(reach, 0) / 100


def tab_settings(palette: list) -> dict[str, str]:
    """The tabs, drawn the way the qtile task list draws windows.

    The task list is the scheme: the bar is ``background``; the focused window is a
    ``highlight`` block with ``background`` text; every other window is ``foreground`` text
    on ``surface``, a step from ``background`` toward ``neutral``. The selected tab and the
    tab bar take the first two as they are.

    The third needs extending, because the task list has one kind of unfocused cell with a
    gap either side and qutebrowser has four kinds -- even and odd, pinned or not -- with no
    gap at all, so neighbours must differ from each other and a pinned tab from a plain one.
    All four stay on the same line from ``background`` toward ``neutral``, so none of them is
    a colour. How far along is not chosen: the line is usable up to the point where
    ``foreground`` stops reading on it (:func:`legible_reach`), and the four are spaced
    evenly over that stretch, plain tabs nearest the bar and pinned ones furthest from it.

    A pinned tab that is selected is the selected tab; qutebrowser's own defaults say the
    same, and its shrunken width already says *pinned*. The selected title is set bold when
    its pair falls short of body-text contrast, the allowance large text gets, and left alone
    when it does not. The load stripe's finished and failed ends take the tokens named for
    exactly that; its starting end has no such token and keeps its match.

    Returns nothing when the palette lacks one of the four tokens or its text does not read
    on its own background, which leaves the tabs to the plain match.
    """
    by_label = {candidate["label"]: candidate["hex"] for candidate in palette}
    if not {"background", "foreground", "neutral", "highlight"} <= set(by_label):
        return {}
    bar, text, neutral = by_label["background"], by_label["foreground"], by_label["neutral"]
    reach = legible_reach(bar, neutral, text)
    if not reach:
        return {}

    settings = {"c.colors.tabs.bar.bg": bar}
    for rung, kind in enumerate(INACTIVE_TABS, start=1):
        surface = color_match.mix(bar, neutral, reach * rung / len(INACTIVE_TABS))
        settings[f"c.colors.tabs.{kind}.bg"] = surface
        settings[f"c.colors.tabs.{kind}.fg"] = text
    for kind in ACTIVE_TABS:
        settings[f"c.colors.tabs.{kind}.bg"] = by_label["highlight"]
        settings[f"c.colors.tabs.{kind}.fg"] = bar
    if (color_match.contrast(bar, by_label["highlight"]) or 0) < color_match.MIN_TEXT_CONTRAST:
        settings["c.fonts.tabs.selected"] = "bold default_size default_family"
    for end, token in INDICATORS.items():
        if token in by_label:
            settings[f"c.colors.tabs.indicator.{end}"] = by_label[token]
    return settings


#: Contrast that still reads for a hint's bold label when body-text contrast is not on offer.
MIN_BOLD_CONTRAST = 3.0


def hint_settings(defaults: dict[str, Any], palette: list) -> dict[str, str]:
    """The link hints, as a pair chosen together: text, the plate under it, and its edge.

    The plate is the grey that stands furthest from the theme's background, the text is that
    background: the strongest pair the palette has, and the inverse of the chrome, so a hint
    does not read as part of the page's own dark or light surface. The already-typed part of
    a hint keeps a colour -- the one nearest qutebrowser's green that still reads on the
    plate, at body-text contrast if any reaches it, else at the bold-text threshold, else
    whichever contrasts most. The border is drawn in the text colour because a white plate
    on a white page is otherwise only its letters.
    """
    by_label = {candidate["label"]: candidate for candidate in palette}
    if "background" not in by_label:
        return {}
    text = by_label["background"]["hex"]
    greys = [c for c in palette if c["label"] in color_match.TEXT_LABELS]
    plate = max(greys, key=lambda c: color_match.contrast(c["hex"], text) or 0)["hex"]
    if plate == text:
        return {}

    def reads(candidate: dict) -> float:
        return color_match.contrast(candidate["hex"], plate) or 0

    others = [c for c in palette if c["hex"] not in (text, plate)]
    stock = defaults.get("c.colors.hints.match.fg", "green")
    matched = text
    for threshold in (color_match.MIN_TEXT_CONTRAST, MIN_BOLD_CONTRAST):
        found = color_match.nearest(stock, [c for c in others if reads(c) >= threshold])
        if found is not None:
            matched = found.hex
            break
    else:
        if others:
            matched = max(others, key=reads)["hex"]
    return {
        "c.colors.hints.bg": plate,
        "c.colors.hints.fg": text,
        "c.colors.hints.match.fg": matched,
        "c.hints.border": f"1px solid {text}",
    }


def page_settings(palette_map: dict[str, list]) -> dict[str, str]:
    """The surface under a page that brings no background: the light one, in both modes.

    A page that sets no background sets no text colour either, so what is drawn over this is
    the browser's black, whatever the theme. The light palette's background is the one
    surface that text reads on. In dark mode it is still right: ``config.py`` switches on
    Chromium's dark mode there, which inverts the page -- surface and text together.
    """
    for candidate in palette_map.get("light", []):
        if candidate["label"] == "background":
            return {"c.colors.webpage.bg": candidate["hex"]}
    return {}


def stock_source() -> str:
    """The dump ``qutebrowser --config-py`` wrote, which carries the defaults."""
    with open(template_path("qutebrowser", "template_config.py")) as handle:
        return handle.read()


def theme_settings(configuration: dict[str, Any], mode: str) -> dict[str, str]:
    """Setting name -> what this theme gives it: ``c.colors.*``, the hint border, a tab font.

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
        candidates = color_match.filter_candidates(name, reference)
        replacement = mapped(value, candidates, lookup)
        if replacement is not None:
            settings[name] = replacement
    settings = with_legible_text(settings, defaults, lookup)
    settings.update(page_settings(palette_map))
    settings.update(hint_settings(defaults, lookup))
    settings.update(tab_settings(lookup))
    return settings


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
        "# keeps its own. The exceptions are the hints, which are declared as a pair, the",
        "# tabs, which are drawn the way the qtile task list draws windows, and the surface",
        "# under a page with no background, which is the light one in both modes.",
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
