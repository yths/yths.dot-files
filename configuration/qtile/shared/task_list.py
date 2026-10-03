"""A task list whose window titles sit on the same centre line as every other cell.

``libqtile.widget.TaskList`` does not centre its text. It draws each title at
``margin_y + padding_y`` from the top of the bar and leaves the rest of the height below
it, so where the text lands depends on a padding someone chose by hand. Every other cell is
a ``TextBox`` underneath, which *does* centre -- on ``(bar.height - layout.height) / 2``.

``config.py`` used to pass ``padding_y = font size / 3``. Measured on the running bar, that
put the titles at rows 20-36 of a 61-pixel bar, centred on row 28 while the clock, the
group boxes and every icon centred on row 35: seven pixels high. It had always been, but
with ASCII group labels nothing tall sat next to the titles to show it, and the first
bundle with full-height glyphs made it obvious.

This derives ``padding_y`` from the height of the font's line once the layout exists, the
same centring the rest of the bar gets, so it holds for any font, size and scaling factor.
The highlight block grows with it and stays symmetric about the centre.
"""

from typing import Any

from libqtile import widget


class CentredTaskList(widget.TaskList):

    def _configure(self, qtile: Any, bar: Any) -> None:
        widget.TaskList._configure(self, qtile, bar)
        spare = self.bar.size - self.layout.height - 2 * (self.margin_y + self.borderwidth)
        self.padding_y = max(spare // 2, 0)
