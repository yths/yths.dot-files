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
from shared.hover_bar import HoverBar


def use_secondary_bar(available: int, minimum: int, secondary: bool) -> bool:
    threshold = minimum * 3 // 2 if secondary else minimum
    return available < threshold


class CentredTaskList(widget.TaskList):
    def __init__(self, **config: Any) -> None:
        super().__init__(**config)
        self.titles_hidden = False

    def _configure(self, qtile: Any, bar: Any) -> None:
        widget.TaskList._configure(self, qtile, bar)
        spare = self.bar.size - self.layout.height - 2 * (self.margin_y + self.borderwidth)
        self.padding_y = max(spare // 2, 0)

    def get_taskname(self, window: Any) -> str:
        name = super().get_taskname(window)
        if window is not None and window.urgent and self.markup_focused:
            return self.markup_focused.format(name)
        return name

    def draw(self) -> None:
        if self.length and self.titles_hidden:
            self._box_end_positions = []
            self.drawer.clear(self.background or self.bar.background)
            self.draw_at_default_position()
        elif self.length:
            super().draw()


class AdaptiveTaskBar(HoverBar):
    def __init__(self, *args: Any, minimum_task_width: int, **kwargs: Any) -> None:
        self.minimum_task_width = minimum_task_width
        super().__init__(*args, **kwargs)

    def _resize(self, length: int, widgets: list[Any]) -> None:
        task = next((item for item in widgets if isinstance(item, CentredTaskList)), None)
        if task is not None and self.screen is not None:
            bottom = self.screen.bottom
            available = max(length - sum(item.length for item in widgets if item is not task), 0)
            secondary = use_secondary_bar(available, self.minimum_task_width, bottom.expanded)
            task.titles_hidden = secondary
            bottom.set_expanded(secondary)
        super()._resize(length, widgets)


class SecondaryTaskBar(HoverBar):
    def __init__(self, *args: Any, outline_size: int, **kwargs: Any) -> None:
        self.outline_size = outline_size
        self.expanded = False
        super().__init__(*args, **kwargs)

    def _configure(self, qtile: Any, screen: Any, reconfigure: bool = False) -> None:
        super()._configure(qtile, screen, reconfigure=reconfigure)
        self._apply_size()

    def set_expanded(self, expanded: bool) -> None:
        if self.expanded != expanded:
            self.expanded = expanded
            self.set_outline_color(self.border_color[2])
            if self.window is not None:
                self._apply_size()
                for edge in (self.screen.left, self.screen.right):
                    if edge is not None and edge._configured:
                        edge._configure(self.qtile, self.screen, reconfigure=True)
                if self.screen.group is not None:
                    self.screen.group.layout_all()

    def set_outline_color(self, colour: str) -> None:
        self.border_color = [self.background if self.expanded else colour, colour, colour, colour]

    def _actual_draw(self) -> None:
        super()._actual_draw()
        if not self.expanded or not hasattr(self, "drawer"):
            return
        top, right, _, left = self.border_width
        width = self.width + left + right
        for x, corner_width, colour in (
            (0, left, self.border_color[3]),
            (width - right, right, self.border_color[1]),
        ):
            if top and corner_width:
                self.drawer.clear_rect(x, 0, corner_width, top)
                self.drawer.ctx.rectangle(x, 0, corner_width, top)
                self.drawer.set_source_rgb(colour)
                self.drawer.ctx.fill()
                self.drawer.draw(offsetx=x, offsety=0, width=corner_width, height=top, src_x=x, src_y=0)

    def _apply_size(self) -> None:
        full_height = self.height + self.border_width[0] + self.border_width[2]
        height = full_height if self.expanded else self.outline_size
        self.fullsize = height
        if height:
            self.window.place(
                self.x,
                self.screen.y + self.screen.height - height,
                self.width + self.border_width[1] + self.border_width[3],
                height,
                0,
                None,
            )
            self.window.unhide()
            self.draw()
        else:
            self.window.hide()
