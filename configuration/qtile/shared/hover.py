"""Expand-on-hover for a ``BackgroundPoll`` bar cell.

A cell mixes this in ahead of ``BackgroundPoll`` and implements ``_render()``, which reads
``self.expanded`` to choose between its compact and its detailed text. Hovering flips the
flag and redraws at once; the poll redraws from the same state, so new data never undoes a
hover. Enter and leave come from ``shared.hover_bar``.
"""

from typing import Any


class HoverExpand:
    expanded: bool = False

    def _render(self) -> str:
        raise NotImplementedError

    def mouse_enter(self, x: int, y: int) -> None:
        self.expanded = True
        self._refresh()

    def mouse_leave(self, x: int, y: int) -> None:
        self.expanded = False
        self._refresh()

    def _refresh(self) -> None:
        """Re-render from the current state. Always called on the event loop."""
        super().update(self._render())  # type: ignore[misc]

    def _pointer_is_on_me(self) -> bool:
        """Whether the pointer is inside this cell, asked of the pointer itself.

        Hover is driven by enter and leave events, which arrive on every pointer motion and
        are what makes the cell react immediately; see ``shared.hover_bar``. This is the
        slow backstop for the one case no motion event covers: the cell changing width under
        a pointer that has not moved, when new data arrives or the theme switches.

        The rectangle has to be the one ``HoverBar.get_widget_in_position`` tests, or the
        two disagree and each poll undoes what the last crossing did. Widgets span the bar
        from ``offsety`` for ``bar.size`` across, which is not the same as ``0`` to
        ``bar.size``: the window is taller than ``size`` by the width of the north border.

        Returns the current flag when the position cannot be read, so an unavailable pointer
        never forces a state change.
        """
        bar: Any = getattr(self, "bar", None)
        window = getattr(bar, "window", None)
        core = getattr(getattr(self, "qtile", None), "core", None)
        if window is None or core is None:
            return self.expanded
        try:
            pointer_x, pointer_y = core.get_mouse_position()
        except (AttributeError, TypeError, OSError):
            return self.expanded
        x = pointer_x - window.x
        y = pointer_y - window.y
        offsetx: int = getattr(self, "offsetx", 0)
        offsety: int = getattr(self, "offsety", 0)
        length: int = getattr(self, "length", 0)
        return offsetx <= x < offsetx + length and offsety <= y < offsety + bar.size

    def update(self, text: str) -> None:
        """Apply the *current* state, not the text handed in.

        ``poll()`` runs on a worker thread, so the string it produced can predate a pointer
        that entered or left while the read was still in flight. Applying that stale
        snapshot made hover sometimes fail to expand, and sometimes fail to contract on
        leave. Re-deriving the flag here costs one pointer query per poll and makes the poll
        unable to contradict the pointer.

        Only the poll path reconciles. The hover handlers call ``_refresh`` directly,
        because they run before the pointer has settled and re-deriving there would fight
        the very event being handled.
        """
        self.expanded = self._pointer_is_on_me()
        self._refresh()
