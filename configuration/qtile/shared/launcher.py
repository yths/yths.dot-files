"""The rofi command line that opens the launcher on the focused screen, inside its outline.

Left to itself rofi picks a monitor and a position on its own terms. Its default monitor is
``-5``, the one under the mouse pointer -- which is not the screen qtile has focused whenever
focus moved by keyboard, or a window opened on the other screen while the pointer stayed
put. And its geometry came from the theme, which ``helper/patch_rofi.py`` writes once from
averages: a width of the whole monitor and an offset of the bar's height without its north
border. On the focused screen that covered the outline's left and right edges and the
bottom of the bar.

qtile knows both facts exactly at the moment of the key press, so it says them: the screen's
output name, and its geometry inside the outline, as a ``-theme-str`` that wins over the
theme's averages. Pure -- the caller reads the numbers off qtile's objects -- so it can be
tested without a window manager.
"""

from typing import NamedTuple


class Clearance(NamedTuple):
    """The focused screen's width, and what the launcher must keep clear of.

    ``top`` is everything above the launcher: the bar and its north border. ``left`` and
    ``right`` are the outline's side edges, zero when the outline is switched off.
    """

    width: int
    top: int
    left: int = 0
    right: int = 0


def rofi_command(
    mode: str, output: str | None, clearance: Clearance, script: str | None = None
) -> list[str]:
    """The argv that shows rofi's ``mode`` on ``output``, clear of the bar and the outline.

    rofi's ``north`` anchor centres the window, so uneven side edges are evened out with
    ``x-offset``. ``script`` makes ``mode`` a script mode backed by that executable -- how the
    power menu is a rofi mode like ``run`` and opens in the same place.
    """
    geometry = (
        f"window {{ width: {clearance.width - clearance.left - clearance.right}px; "
        f"x-offset: {(clearance.left - clearance.right) // 2}px; "
        f"y-offset: {clearance.top}px; }}"
    )
    command = ["rofi", "-show", mode]
    if script:
        command += ["-modi", f"{mode}:{script}"]
    if output:
        command += ["-m", output]
    return [*command, "-theme-str", geometry]
