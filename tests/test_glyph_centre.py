"""A lone glyph sits on the bar's centre line, whatever font and symbol the theme picks.

qtile centres the font's line box, not the ink. The backend indicator is a single dot, and
the dot of one face sat visibly lower in the bar than the dot of another. The cell is now
placed by where its ink is.
"""

import types

import cairocffi
import pytest
import shared.glyph_centre
import symbols
from libqtile import pangocffi
from widgets.service_state import WidgetServiceState

#: The faces the shipped bundles name. A test skips the one this machine does not have.
FACES = ["Atkinson Mono NF", "Iosevka NF"]
#: (font size in pixels, bar height): the bar is 2.75 font sizes high, and the two pairs
#: differ in whether the line height and the bar agree about parity.
SIZES = [(19, 52), (22, 61), (28, 77)]
#: A dot at three heights in the line, an icon, an ASCII stand-in, and a glyph with a descender.
TEXTS = ["·", ".", "'", "\U000f09df", "\U000f04b2 ", "zzz ", "g"]


def _inked_rows(text: str, face: str, size: int, height: int, top: float) -> tuple[int, int]:
    """The first inked row and the row after the last, drawing the way the bar does."""
    surface = cairocffi.ImageSurface(cairocffi.FORMAT_A8, size * 8, height)
    context = cairocffi.Context(surface)
    layout = pangocffi.create_layout(context)
    layout.set_font_description(pangocffi.FontDescription.from_string(f"{face} {size}px"))
    layout.set_text(text)
    context.move_to(size * 2, top)
    pangocffi.show_layout(context, layout)
    surface.flush()
    data, stride, width = bytes(surface.get_data()), surface.get_stride(), surface.get_width()
    inked = [
        row for row in range(height)
        if any(value > 127 for value in data[row * stride : row * stride + width])
    ]
    return inked[0], inked[-1] + 1


def _installed(face: str) -> bool:
    """Whether fontconfig resolves ``face`` to itself: its icon is drawn, and a middle dot
    and a full stop sit at different heights, which a missing face's fallback need not do."""
    return shared.glyph_centre.ink_centre("\U000f09df", face, 20) is not None


@pytest.mark.parametrize("face", FACES)
@pytest.mark.parametrize(("size", "height"), SIZES)
def test_every_glyph_is_centred_to_the_pixel(face: str, size: int, height: int) -> None:
    if not _installed(face):
        pytest.skip(f"{face} is not installed")
    for text in TEXTS:
        top = shared.glyph_centre.top(text, face, size, height)
        assert isinstance(top, int), text
        first, after = _inked_rows(text, face, size, height, top)
        # Half a pixel is the parity of the ink against the bar, which no position removes.
        assert abs((first + after) / 2 - height / 2) <= 0.5, (text, first, after)


@pytest.mark.parametrize("face", FACES)
def test_qtile_alone_leaves_a_dot_off_centre(face: str) -> None:
    """The defect: the line box centred one pixel down, as ``_TextBox.draw`` places it."""
    if not _installed(face):
        pytest.skip(f"{face} is not installed")
    size, height = 19, 52
    probe = cairocffi.Context(cairocffi.ImageSurface(cairocffi.FORMAT_A8, 1, 1))
    layout = pangocffi.create_layout(probe)
    layout.set_font_description(pangocffi.FontDescription.from_string(f"{face} {size}px"))
    layout.set_text(".")
    line = layout.get_pixel_size()[1]
    first, after = _inked_rows(".", face, size, height, round((height - line) / 2 + 1))
    assert (first + after) / 2 - height / 2 > 2, "a full stop sits well below the centre line"


def test_nothing_to_measure_keeps_qtiles_position() -> None:
    assert shared.glyph_centre.top("·", None, 19, 52) is None
    assert shared.glyph_centre.top("·", FACES[0], None, 52) is None
    # The dot blinks: every other second the cell is one space, which has no ink.
    assert shared.glyph_centre.top(" ", FACES[0], 19, 52) is None
    assert shared.glyph_centre.top("", FACES[0], 19, 52) is None


def _cell(text: str) -> WidgetServiceState:
    widget = WidgetServiceState(service="backend.service", symbols=symbols.SYMBOLS, font="Some Face", fontsize=19)
    widget.layout = types.SimpleNamespace(text=text)
    widget.bar = types.SimpleNamespace(size=52)
    return widget


def test_the_cell_draws_at_the_measured_position(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[tuple[str, str, int, int]] = []

    def top(text: str, family: str, size: int, height: int) -> int:
        asked.append((text, family, size, height))
        return 12

    monkeypatch.setattr(shared.glyph_centre, "top", top)
    assert _cell("·")._top(14.5) == 12
    assert asked == [("·", "Some Face", 19, 52)]


def test_the_cell_falls_back_to_qtiles_position(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shared.glyph_centre, "top", lambda *_arguments: None)
    assert _cell(" ")._top(14.5) == 14.5


def test_the_layout_is_drawn_through_the_cell(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_configure`` wraps the layout's draw, so qtile's own ``draw`` uses the position."""
    drawn: list[tuple[float, float]] = []
    layout = types.SimpleNamespace(text="·", draw=lambda x, y: drawn.append((x, y)))

    def configure(self: WidgetServiceState, _qtile: object, bar: object) -> None:
        self.layout, self.bar = layout, bar

    monkeypatch.setattr("libqtile.widget.base.BackgroundPoll._configure", configure)
    monkeypatch.setattr(shared.glyph_centre, "top", lambda *_arguments: 12)
    widget = WidgetServiceState(service="backend.service", symbols=symbols.SYMBOLS, font="Some Face", fontsize=19)
    widget._configure(None, types.SimpleNamespace(size=52))
    widget.layout.draw(5, 14.5)
    assert drawn == [(5, 12)]
