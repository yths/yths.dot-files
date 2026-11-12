"""A bar that tells its widgets where the pointer is, every time it moves.

``libqtile.bar.Bar`` loses hover events two ways, and a widget that changes shape on hover
shows both as the same symptom: it reacts late, or not at all, and which of the two you get
depends on how fast the pointer was moving.

**The hit test misses a strip of the bar.** ``get_widget_in_position`` bounds a horizontal
bar's vertical test with ``border_width[3] <= y < self.size`` -- the *west* border as the
lower bound, and the content height as the upper one. The window is ``border_width[0] +
size`` tall, so a strip as tall as the north border, along the bottom edge of the bar,
belongs to a widget visually but answers ``None``. On this desktop that is the bottom five
pixels: measured on the running bar, the pointer at y=65 of a 68-pixel bar was over the
widget's own cell and the bar reported nothing there.

**Nothing is dispatched unless both sides are widgets.** The guard reads ``if widget and
self._has_cursor and widget is not self._has_cursor``, so moving *onto* a widget from
nowhere sends no enter, and moving from a widget to nowhere sends no leave -- while
``_has_cursor`` is assigned either way. One crossing of that bottom strip therefore clears
the record without telling the widget, and the next crossing back finds ``_has_cursor``
empty and stays silent too. ``process_pointer_leave`` then has nothing to notify, so a cell
can stay expanded with the pointer somewhere else entirely.

Together they make hover feel random, because the strip is only five pixels: move the
pointer quickly and X's motion compression steps over it, the transition is between two
widgets, and hover works. Move it slowly and every crossing lands in the strip.

This subclass fixes the bounds and dispatches on every change, including to and from
``None``. Widgets get their enter and leave from pointer motion, which arrives continuously,
so feedback is immediate and nothing has to be polled.
"""

from typing import TYPE_CHECKING

import libqtile.bar

if TYPE_CHECKING:
    from libqtile.widget.base import _Widget


class HoverBar(libqtile.bar.Bar):
    """``libqtile.bar.Bar`` with a hit test that covers the bar and lossless dispatch."""

    def get_widget_in_position(self, x: int, y: int) -> _Widget | None:
        """The widget under ``(x, y)``, measured against where widgets are actually drawn.

        Widgets run along the bar from ``border_width[3]`` (horizontal) or
        ``border_width[0]`` (vertical), each spanning the full ``size`` across it, starting
        at the border on that side. Both axes are bounded here; the base class bounds
        neither the far edge across the bar nor the near edge along it.
        """
        if self.horizontal:
            along, across = x, y
            along_start, across_start = self.border_width[3], self.border_width[0]
        else:
            along, across = y, x
            along_start, across_start = self.border_width[0], self.border_width[3]

        if not across_start <= across < across_start + self.size:
            return None
        if along < along_start:
            return None
        for widget in self.widgets:
            offset = widget.offsetx if self.horizontal else widget.offsety
            if along < offset + widget.length:
                return widget
        return None

    def _hand_cursor_to(self, widget: _Widget | None, x: int, y: int) -> None:
        """Move the cursor to ``widget``, telling both sides. ``None`` means off the bar."""
        if widget is self._has_cursor:
            return
        if self._has_cursor is not None:
            self._has_cursor.mouse_leave(
                x - self._has_cursor.offsetx, y - self._has_cursor.offsety
            )
        if widget is not None:
            widget.mouse_enter(x - widget.offsetx, y - widget.offsety)
        self._has_cursor = widget

    def process_pointer_enter(self, x: int, y: int) -> None:
        self._hand_cursor_to(self.get_widget_in_position(x, y), x, y)

    def process_pointer_motion(self, x: int, y: int) -> None:
        self._hand_cursor_to(self.get_widget_in_position(x, y), x, y)

    def process_pointer_leave(self, x: int, y: int) -> None:
        self._hand_cursor_to(None, x, y)
