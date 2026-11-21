"""An even gap after an icon, whatever the icon's own width.

A Nerd Font icon does not fill its cell the way a letter does. In the bar's monospace face
every glyph advances by one cell, but the Material Design icons are drawn up to half a cell
*past* theirs -- the keyboard overhangs by a third of a cell, the mouse by a twentieth -- and
the stock bluetooth rune stops short of it. Follow each with the same space character and the
distance from ink to whatever comes next differs by icon: measured in Atkinson Mono NF, from
0.55 of a cell after a gamepad to 1.08 after the bluetooth rune.

So the space is sized per icon. The icon is laid out once, off screen, by the same Pango the
bar draws with; where its ink ends is read off the pixels; and the space after it is scaled
so the ink-to-neighbour distance comes to :data:`GAP` of a cell for every icon. Nothing is
looked up in the font file and nothing is tabulated by glyph, so a different face, size or
icon is measured the same way the first time it is drawn.
"""

import functools

import cairocffi
from libqtile import pangocffi

#: The clear distance wanted between an icon's ink and what follows, in cells. Half a cell
#: is the width of a word space in a proportional face, which is what this stands in for.
GAP = 0.5

#: Cells of canvas the icon is measured on: wider than any icon overhangs.
_CANVAS_CELLS = 4


def _layout(context: cairocffi.Context, family: str, size: int, text: str) -> pangocffi.PangoLayout:
    layout = pangocffi.create_layout(context)
    layout.set_font_description(pangocffi.FontDescription.from_string(f"{family} {size}px"))
    layout.set_text(text)
    return layout


@functools.cache
def overhang(glyph: str, family: str, size: int) -> float | None:
    """How far ``glyph``'s ink runs past its advance, in cells; negative when it stops short.

    ``None`` when nothing was drawn -- a glyph the face lacks and no fallback supplies.
    """
    probe = cairocffi.Context(cairocffi.ImageSurface(cairocffi.FORMAT_A8, 1, 1))
    advance, height = _layout(probe, family, size, glyph).get_pixel_size()
    if advance <= 0 or height <= 0:
        return None

    surface = cairocffi.ImageSurface(cairocffi.FORMAT_A8, advance * _CANVAS_CELLS, height)
    context = cairocffi.Context(surface)
    pangocffi.show_layout(context, _layout(context, family, size, glyph))
    surface.flush()
    data, stride = bytes(surface.get_data()), surface.get_stride()
    inked = [
        column
        for column in range(surface.get_width())
        if any(data[row * stride + column] > 127 for row in range(height))
    ]
    if not inked:
        return None
    return (inked[-1] + 1 - advance) / advance


def after(glyph: str, family: str | None, size: int | None) -> str:
    """Pango markup for the space that follows ``glyph``, sized to leave :data:`GAP` clear.

    A plain space when there is nothing to measure: no font yet, a multi-character ASCII
    stand-in whose letters fill their cells, or a glyph that could not be drawn.
    """
    if not family or not size or len(glyph) != 1:
        return " "
    past = overhang(glyph, family, int(size))
    if past is None:
        return " "
    scale = round((GAP + past) * 100)
    return f"<span font_size='{scale}%'> </span>" if scale > 0 else ""
