"""Hover dispatch: the bar must tell a widget the moment the pointer arrives or leaves.

Both sequences here were measured on the running bar before the fix, with the pointer driven
by xdotool. The bar was 68 pixels tall with `size` 63 and a 5-pixel north border, and the
claude widget's cell ran x 2597..2661:

    pointer y=30   expanded=True   has_cursor=WidgetClaudeUsage   hit=WidgetClaudeUsage
    pointer y=65   expanded=True   has_cursor=None                hit=None
    pointer y=100  expanded=True   has_cursor=None                hit=None

-- the cell still expanded with the pointer off the bar entirely -- and, approaching from
below through the same strip, the cell stayed collapsed until the five-second poll caught up.
"""

import shared.hover_bar


class Widget:
    """The parts of a widget the bar's dispatch touches."""

    def __init__(self, offsetx: int, length: int, offsety: int = 5) -> None:
        self.offsetx, self.offsety, self.length = offsetx, offsety, length
        self.events: list[str] = []

    def mouse_enter(self, x: int, y: int) -> None:
        self.events.append("enter")

    def mouse_leave(self, x: int, y: int) -> None:
        self.events.append("leave")


class Bar(shared.hover_bar.HoverBar):
    """A HoverBar with the measured geometry, built without qtile's configure step."""

    def __init__(self) -> None:
        self.horizontal = True
        self.size = 63
        self.border_width = [5, 5, 0, 5]
        self._has_cursor = None
        self.left = Widget(offsetx=5, length=2592)
        self.claude = Widget(offsetx=2597, length=64)
        self.widgets = [self.left, self.claude]


def test_the_whole_bar_belongs_to_a_widget() -> None:
    """The measured failure: y=65 is inside a 68-pixel bar and hit nothing."""
    bar = Bar()
    assert bar.get_widget_in_position(2620, 65) is bar.claude
    assert bar.get_widget_in_position(2620, 30) is bar.claude


def test_the_north_border_is_not_a_widget() -> None:
    """Widgets start at offsety; above that is the focus outline, which nothing owns."""
    assert Bar().get_widget_in_position(2620, 2) is None


def test_past_the_last_widget_is_nothing() -> None:
    assert Bar().get_widget_in_position(9999, 30) is None


def test_leaving_the_bar_downwards_contracts_the_cell() -> None:
    """The first measured sequence, in full."""
    bar = Bar()
    bar.process_pointer_motion(2620, 30)
    assert bar.claude.events == ["enter"]
    bar.process_pointer_motion(2620, 65)      # the strip that used to swallow the leave
    bar.process_pointer_leave(2620, 100)
    assert bar.claude.events == ["enter", "leave"]
    assert bar._has_cursor is None


def test_arriving_from_below_expands_the_cell() -> None:
    """The second: crossing the strip must not leave the widget unaware."""
    bar = Bar()
    for y in (67, 65, 63, 60, 40, 30):
        bar.process_pointer_motion(2620, y)
    assert bar.claude.events == ["enter"]


def test_entering_from_nowhere_still_enters() -> None:
    """qtile's guard needed both sides to be widgets; this is the half that was dropped."""
    bar = Bar()
    bar.process_pointer_enter(2620, 30)
    assert bar.claude.events == ["enter"]


def test_moving_between_widgets_swaps_the_cursor() -> None:
    bar = Bar()
    bar.process_pointer_motion(100, 30)
    bar.process_pointer_motion(2620, 30)
    assert bar.left.events == ["enter", "leave"]
    assert bar.claude.events == ["enter"]


def test_staying_put_says_nothing_twice() -> None:
    """Motion within one cell must not re-fire, or the cell redraws on every pixel."""
    bar = Bar()
    for x in range(2600, 2660, 5):
        bar.process_pointer_motion(x, 30)
    assert bar.claude.events == ["enter"]


def test_a_vertical_bar_measures_the_other_way() -> None:
    bar = Bar()
    bar.horizontal = False
    bar.left.offsety, bar.left.length = 5, 100
    bar.claude.offsety, bar.claude.length = 105, 60
    assert bar.get_widget_in_position(30, 130) is bar.claude
    assert bar.get_widget_in_position(2, 130) is None
