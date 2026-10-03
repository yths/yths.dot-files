"""The window titles have to share the centre line the rest of the bar's cells sit on.

qtile's TaskList draws its text at ``margin_y + padding_y`` from the top of the bar rather
than centring it. With the hand-picked padding config.py used to pass, the titles on a
61-pixel bar were measured at rows 20-36 while the clock and every icon centred on row 35.
"""

import types

import pytest
import shared.task_list
from libqtile import widget


def _configured(monkeypatch: pytest.MonkeyPatch, *, bar: int, line: int) -> widget.TaskList:
    """A CentredTaskList after configure, with qtile's own step replaced by its outcome."""
    task_list = shared.task_list.CentredTaskList(margin_y=3, borderwidth=0)

    def stock_configure(self: widget.TaskList, _qtile: object, configured_bar: object) -> None:
        self.bar = configured_bar
        self.layout = types.SimpleNamespace(height=line)

    monkeypatch.setattr(widget.TaskList, "_configure", stock_configure)
    task_list._configure(None, types.SimpleNamespace(size=bar, horizontal=True))
    return task_list


# The text is drawn at margin_top + padding_top, and is a line high: centred, the space
# above it and the space below it are equal.
@pytest.mark.parametrize(("bar", "line"), [(61, 29), (63, 29), (40, 18), (68, 33)])
def test_the_title_is_centred_in_the_bar(
    monkeypatch: pytest.MonkeyPatch, bar: int, line: int
) -> None:
    task_list = _configured(monkeypatch, bar=bar, line=line)
    above = task_list.margin_top + task_list.padding_top
    below = bar - above - line
    assert abs(above - below) <= 1, f"{above} above the title, {below} below it"


# A font taller than the bar cannot be centred by negative padding; it is drawn from the top.
def test_a_line_taller_than_the_bar_gets_no_negative_padding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _configured(monkeypatch, bar=20, line=40).padding_y == 0
