"""A glyph on the bar's centre line, whatever height its font draws it at.

qtile centres a cell's *line*: it puts the font's line box in the middle of the bar, one
pixel down, which suits capitals and digits. Where a glyph sits inside that box is the font's
business. A middle dot rides at about half the x-height, and the x-height differs per face:
measured in the bar, the same dot is 0.7px below centre in Iosevka NF and 1.8px below in
Atkinson Mono NF. A Nerd Font icon is centred in the box, so it lands on qtile's one pixel
down and on a half pixel more whenever the line height and the bar disagree about parity.
None of that shows in a row of digits. It shows in a cell that is one small dot.

So the line is placed by its ink. The text is laid out once, off screen, by the same Pango
the bar draws with; the rows its ink covers are read off the pixels; and the line's top is
chosen so the middle of those rows is the middle of the bar. Nothing is looked up in the
font file and nothing is tabulated by glyph: a different face, size or symbol is measured
the same way the first time it is drawn. See ``glyph_gap.py`` for the horizontal twin.
"""

import functools
import math

import cairocffi
from libqtile import pangocffi

#: Columns of canvas either side of the text's advance, in font sizes: wider than any icon
#: overhangs, so ink past the advance is still seen.
_MARGIN = 2


def _layout(context: cairocffi.Context, family: str, size: int, text: str) -> pangocffi.PangoLayout:
    layout = pangocffi.create_layout(context)
    layout.set_font_description(pangocffi.FontDescription.from_string(f"{family} {size}px"))
    layout.set_text(text)
    return layout


@functools.cache
def ink_centre(text: str, family: str, size: int) -> float | None:
    """The middle of the rows ``text``'s ink covers, in pixels below the top of its line.

    ``None`` when nothing was drawn: blank text, or a glyph the face lacks and no fallback
    supplies.
    """
    probe = cairocffi.Context(cairocffi.ImageSurface(cairocffi.FORMAT_A8, 1, 1))
    advance, height = _layout(probe, family, size, text).get_pixel_size()
    if advance <= 0 or height <= 0:
        return None

    surface = cairocffi.ImageSurface(cairocffi.FORMAT_A8, advance + 2 * _MARGIN * size, height)
    context = cairocffi.Context(surface)
    context.move_to(_MARGIN * size, 0)
    pangocffi.show_layout(context, _layout(context, family, size, text))
    surface.flush()
    data, stride, width = bytes(surface.get_data()), surface.get_stride(), surface.get_width()
    inked = [row for row in range(height) if any(value > 127 for value in data[row * stride : row * stride + width])]
    if not inked:
        return None
    return (inked[0] + inked[-1] + 1) / 2


def top(text: str, family: str | None, size: float | None, height: int) -> int | None:
    """Where the top of ``text``'s line goes so its ink is centred in ``height`` pixels.

    A whole pixel, because that is where the off-screen measurement drew it: half a pixel
    here would be rasterised differently and move the ink the measurement just placed. An
    exact tie goes down, the way qtile's own one pixel does. ``None`` when there is nothing
    to measure -- no font yet, or no ink -- and the caller keeps qtile's position.
    """
    if not family or not size:
        return None
    centre = ink_centre(text, family, int(size))
    if centre is None:
        return None
    return math.floor(height / 2 - centre + 0.5)
