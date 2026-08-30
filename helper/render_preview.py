"""Render a preview of the configured desktop from the palette, not from a screen.

A screenshot of the running desktop would carry whatever happened to be on it — window
titles, file names, the bar's VPN country and usage figures. This draws the same surfaces
from the theme bundle instead: the bar, a terminal, a notification. Nothing here reads the
session, so there is nothing in the output that was not already in ``assets/``.

    python helper/render_preview.py            # both variants into docs/preview/
    python helper/render_preview.py --mode dark

Regenerated only when the default theme changes or an application is added, which is why the
output is tracked rather than gitignored: unlike the per-app configuration the patchers
write, this does not change twice a day.
"""

import argparse
import hashlib
import json
import os
import pickle
import sys
from typing import Any

import cairo

try:
    from helper.utils import logger, read_setup
except ImportError:
    from utils import logger, read_setup

#: This file's repository, resolved through any symlink used to invoke it.
_REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
OUTPUT_ROOT = os.path.join(_REPOSITORY_ROOT, "docs", "preview")

#: Written beside the images, holding a digest of what they were drawn from. gendocs compares
#: it against the current palette, so a theme change that forgets to re-render is caught at
#: the commit rather than noticed in the README months later.
DIGEST_PATH = os.path.join(OUTPUT_ROOT, "rendered-from.txt")

WIDTH, HEIGHT = 1120, 452
MARGIN = 32
BAR_HEIGHT = 34
RADIUS = 8

#: The bar's cells, as (glyph, palette token). Nerd-font private-use codepoints are escaped
#: with the glyph named alongside: they are invisible in an editor and dropped by anything
#: that rewrites the line.
BAR_CELLS = (
    (" 06:32", "foreground"),        # sunrise
    (" 20:15", "highlight"),         # sunset
    ("\U000f02ce ▅", "foreground"),   # headphones + level
    ("\U000f0c9d", "foreground_variant"),  # shield-off, VPN
    ("\U000f06a5", "success"),             # battery-charging
    ("\U000f06b0 3", "notification"),      # package-up, updates
)

#: The sixteen terminal slots, in the order helper/patch_kitty.py assigns them.
ANSI_TOKENS = (
    "foreground_variant", "red", "green", "yellow", "blue", "magenta", "cyan", "background",
    "foreground", "red_variant", "green_variant", "yellow_variant", "blue_variant",
    "magenta_variant", "cyan_variant", "neutral",
)

TERMINAL_LINES = (
    ("$ ", "success", "gendocs.py --check", "foreground"),
    ("", "foreground", "All blocks up to date.", "foreground_variant"),
    ("$ ", "success", "pytest", "foreground"),
    ("", "foreground", "91 passed in 0.46s", "green"),
)


def rgb(hex_colour: str) -> tuple[float, float, float]:
    """``#rrggbb`` to the 0..1 triple cairo wants."""
    return tuple(int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5))


class Painter:
    """A cairo context that speaks in palette tokens rather than colours.

    Every surface drawn here takes its colour from the same palette the desktop does, so the
    preview cannot drift from the theme by being edited independently. Carrying the palette
    and the font on the painter is also what keeps each draw call down to what it is drawing.
    """

    def __init__(self, palette: dict[str, str], font: str) -> None:
        self.palette = palette
        self.font = font
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)
        self.context = cairo.Context(self.surface)
        self.fill("background")
        self.context.paint()

    def fill(self, token: str) -> None:
        self.context.set_source_rgb(*rgb(self.palette[token]))

    def rounded(self, rect: tuple[float, float, float, float], radius: float = RADIUS) -> None:
        x, y, w, h = rect
        self.context.new_sub_path()
        self.context.arc(x + w - radius, y + radius, radius, -1.5708, 0)
        self.context.arc(x + w - radius, y + h - radius, radius, 0, 1.5708)
        self.context.arc(x + radius, y + h - radius, radius, 1.5708, 3.1416)
        self.context.arc(x + radius, y + radius, radius, 3.1416, 4.7124)
        self.context.close_path()

    def panel(self, rect: tuple[float, float, float, float], border: str = "neutral") -> None:
        """A rounded card on the background, outlined in ``border``."""
        self.rounded(rect)
        self.fill("background")
        self.context.fill_preserve()
        self.fill(border)
        self.context.set_line_width(1)
        self.context.stroke()

    def measure(self, string: str, size: float) -> float:
        self.context.select_font_face(self.font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        self.context.set_font_size(size)
        return self.context.text_extents(string).x_advance

    def text(self, position: tuple[float, float], string: str, token: str,
             size: float = 15) -> float:
        """Draw ``string`` and return the x the next run would start at."""
        x, y = position
        self.context.select_font_face(self.font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        self.context.set_font_size(size)
        self.fill(token)
        self.context.move_to(x, y)
        self.context.show_text(string)
        return x + self.context.text_extents(string).x_advance

    def save(self, path: str) -> None:
        self.surface.write_to_png(path)


def draw_bar(painter: Painter) -> None:
    """The qtile bar: group labels on the left, widget cells on the right."""
    x = MARGIN
    for index, label in enumerate("jkl;"):
        token = "highlight" if index == 0 else "neutral"
        x = painter.text((x, 23), label, token) + 14

    right = WIDTH - MARGIN
    for glyph, token in reversed(BAR_CELLS):
        right -= painter.measure(glyph, 15) + 22
        painter.text((right, 23), glyph, token)

    painter.fill("neutral")
    painter.context.rectangle(0, BAR_HEIGHT, WIDTH, 1)
    painter.context.fill()


def draw_terminal(painter: Painter, rect: tuple[float, float, float, float]) -> None:
    """A terminal showing a prompt and the sixteen colours patch_kitty assigns."""
    x, y, w, _height = rect
    painter.panel(rect)

    line_y = y + 42
    for prefix, prefix_token, body, body_token in TERMINAL_LINES:
        cursor = painter.text((x + 24, line_y), prefix, prefix_token)
        painter.text((cursor, line_y), body, body_token)
        line_y += 30

    line_y += 14
    swatch = (w - 48) / len(ANSI_TOKENS)
    for index, token in enumerate(ANSI_TOKENS):
        painter.context.rectangle(x + 24 + index * swatch, line_y, swatch - 3, 26)
        painter.fill(token)
        painter.context.fill_preserve()
        # Slots 7 and 8 are the background and foreground, so one always matches the surface
        # behind it; an outline keeps the strip sixteen swatches wide either way.
        painter.fill("neutral")
        painter.context.set_line_width(1)
        painter.context.stroke()
    painter.text((x + 24, line_y + 52),
                 "16 terminal colours, mapped from the palette", "foreground_variant", 12)


def draw_notification(painter: Painter, rect: tuple[float, float, float, float]) -> None:
    """A dunst notification, in the colours patch_dunst writes."""
    x, y, *_ = rect
    painter.panel(rect, border="notification")
    painter.text((x + 20, y + 38), "Patching", "notification")
    painter.text((x + 20, y + 66), "All configurations reloaded", "foreground", 14)


def draw_palette(painter: Painter, position: tuple[float, float]) -> None:
    """The tokens themselves, so the preview shows what it was drawn from."""
    x, y = position
    painter.text((x, y), "palette", "foreground_variant", 12)
    tokens = [token for token in sorted(painter.palette) if not token.endswith("_variant")]
    for index, token in enumerate(tokens):
        column, row = index % 5, index // 5
        painter.rounded((x + column * 40, y + 16 + row * 40, 32, 32), 4)
        painter.fill(token)
        painter.context.fill_preserve()
        painter.fill("neutral")
        painter.context.set_line_width(1)
        painter.context.stroke()


def render(palette: dict[str, str], font: str, path: str) -> None:
    """Draw every surface in one palette variant and save it."""
    painter = Painter(palette, font)
    terminal = (MARGIN, BAR_HEIGHT + 44, 640, 300)
    aside_x = MARGIN + 640 + 32
    aside_width = WIDTH - MARGIN - aside_x

    draw_bar(painter)
    draw_terminal(painter, terminal)
    draw_notification(painter, (aside_x, terminal[1], aside_width, 118))
    draw_palette(painter, (aside_x, terminal[1] + 150))
    painter.text((MARGIN, HEIGHT - 24),
                 "rendered from the theme bundle — no session data", "neutral", 12)
    painter.save(path)


def palette_digest(palette: dict[str, Any], font: str) -> str:
    """A stable fingerprint of everything the preview is drawn from."""
    material = json.dumps({"palette": palette, "font": font}, sort_keys=True)
    return hashlib.sha256(material.encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=["light", "dark"], default=None,
                        help="render one variant (default: both)")
    arguments = parser.parse_args()

    setup = read_setup()
    bundle = os.path.join(_REPOSITORY_ROOT, "assets", setup["desktop"]["theme"])
    with open(os.path.join(bundle, "palette.pkl"), "rb") as handle:
        palette: dict[str, Any] = pickle.load(handle)

    font = setup["desktop"]["font_family"]
    os.makedirs(OUTPUT_ROOT, exist_ok=True)
    modes = [arguments.mode] if arguments.mode else ["light", "dark"]
    for mode in modes:
        path = os.path.join(OUTPUT_ROOT, f"{mode}.png")
        render(palette[mode], font, path)
        logger.info(f"Rendered {path}")
    if len(modes) == 2:
        with open(DIGEST_PATH, "w") as handle:
            handle.write(palette_digest(palette, font) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
