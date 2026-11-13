"""The window titles have to share the centre line the rest of the bar's cells sit on.

qtile's TaskList draws its text at ``margin_y + padding_y`` from the top of the bar rather
than centring it. With the hand-picked padding config.py used to pass, the titles on a
61-pixel bar were measured at rows 20-36 while the clock and every icon centred on row 35.
"""

import json
import os
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest
import shared.task_list
from libqtile import bar, widget


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


@pytest.mark.parametrize("state", ["normal", "floating", "minimized", "maximized"])
def test_urgent_titles_use_the_focused_text_colour(state: str) -> None:
    task = shared.task_list.CentredTaskList(markup_focused="<span foreground='#123456'>{}</span>")
    task.markup = True
    window = types.SimpleNamespace(
        name="Window <title>",
        urgent=True,
        minimized=state == "minimized",
        maximized=state == "maximized",
        floating=state == "floating",
        group=types.SimpleNamespace(current_window=None),
    )

    urgent = task.get_taskname(window)
    assert urgent.startswith("<span foreground='#123456'>")
    assert "Window &lt;title&gt;" in urgent
    window.urgent = False
    assert urgent == task.markup_focused.format(task.get_taskname(window))


def test_urgent_and_focused_titles_match_without_changing_normal_titles() -> None:
    task = shared.task_list.CentredTaskList(markup_focused="<span foreground='#123456'>{}</span>")
    task.markup = True
    window = types.SimpleNamespace(
        name="Window", urgent=False, minimized=False, maximized=False, floating=False,
        group=types.SimpleNamespace(current_window=None),
    )
    assert task.get_taskname(window) == "Window"
    window.group.current_window = window
    focused = task.get_taskname(window)
    window.group.current_window = None
    window.urgent = True
    assert task.get_taskname(window) == focused


@pytest.mark.parametrize(
    ("available", "secondary", "expected"),
    [(199, False, True), (200, False, False), (200, True, True), (299, True, True), (300, True, False)],
)
def test_secondary_bar_has_a_stable_width_threshold(
    available: int, secondary: bool, expected: bool
) -> None:
    assert shared.task_list.use_secondary_bar(available, 200, secondary) is expected


def test_task_list_moves_based_on_actual_available_space() -> None:
    task = shared.task_list.CentredTaskList()
    left = widget.Spacer(length=300)
    right = widget.Spacer(length=200)
    bottom = shared.task_list.SecondaryTaskBar([], 40, outline_size=3)
    top = shared.task_list.AdaptiveTaskBar([left, task, right], 40, minimum_task_width=200)
    top.screen = types.SimpleNamespace(bottom=bottom)
    top.horizontal = True

    top._resize(650, top.widgets)
    assert bottom.expanded
    assert task.titles_hidden
    assert task.length_type == bar.STRETCH
    assert task.length == 150
    assert right.offsetx + right.length == 650

    top._resize(750, top.widgets)
    assert bottom.expanded
    assert task.length == 250
    assert right.offsetx + right.length == 750
    top._resize(800, top.widgets)
    assert not bottom.expanded
    assert not task.titles_hidden
    assert task.length_type == bar.STRETCH
    assert task.length == 300
    assert right.offsetx + right.length == 800


def test_hidden_task_list_clears_its_cell_and_click_targets() -> None:
    task = shared.task_list.CentredTaskList()
    task.titles_hidden = True
    task.length = 100
    task.bar = types.SimpleNamespace(background="#111111")
    task.drawer = Mock()
    task.draw_at_default_position = Mock()
    task._box_end_positions = [50]

    task.draw()

    task.drawer.clear.assert_called_once_with("#111111")
    task.draw_at_default_position.assert_called_once()
    assert task._box_end_positions == []


@pytest.mark.parametrize("outline", [0, 3])
def test_secondary_bar_reserves_space_only_when_expanded(outline: int) -> None:
    bottom = shared.task_list.SecondaryTaskBar([], 40, outline_size=outline)
    left = Mock()
    left._configured = True
    bottom.screen = types.SimpleNamespace(y=100, height=800, group=Mock(), left=left, right=None)
    bottom.window = Mock()
    bottom.x, bottom.width, bottom.height = 0, 1000 - 2 * outline, 40
    bottom.border_width = [outline] * 4
    bottom.draw = Mock()

    bottom.set_expanded(True)
    assert bottom.fullsize == 40 + 2 * outline
    bottom.window.place.assert_called_with(0, 900 - bottom.fullsize, 1000, bottom.fullsize, 0, None)

    bottom.set_expanded(False)
    assert bottom.fullsize == outline
    if outline:
        bottom.window.place.assert_called_with(0, 900 - outline, 1000, outline, 0, None)
    else:
        bottom.window.hide.assert_called_once()
    assert bottom.screen.group.layout_all.call_count == 2
    assert left._configure.call_count == 2


def test_secondary_bar_draws_only_the_outer_focus_edge() -> None:
    bottom = shared.task_list.SecondaryTaskBar(
        [], 40, outline_size=3, background="#111111", border_color="#222222"
    )

    bottom.set_outline_color("#ff0000")
    assert bottom.border_color == ["#ff0000"] * 4
    bottom.set_expanded(True)
    assert bottom.border_color == ["#111111", "#ff0000", "#ff0000", "#ff0000"]
    bottom.set_outline_color("#00ff00")
    assert bottom.border_color == ["#111111", "#00ff00", "#00ff00", "#00ff00"]
    bottom.set_expanded(False)
    assert bottom.border_color == ["#00ff00"] * 4


def test_secondary_bar_connects_the_focus_outline_at_both_corners(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bottom = shared.task_list.SecondaryTaskBar(
        [], 40, outline_size=3, background="#111111", border_color="#ff0000"
    )
    bottom.border_width = [3] * 4
    bottom.width = 994
    bottom.drawer = Mock()
    bottom.set_expanded(True)
    monkeypatch.setattr(shared.task_list.HoverBar, "_actual_draw", lambda self: None)

    bottom._actual_draw()
    assert bottom.drawer.clear_rect.call_args_list == [
        ((0, 0, 3, 3),),
        ((997, 0, 3, 3),),
    ]
    assert bottom.drawer.set_source_rgb.call_args_list == [(("#ff0000",),)] * 2


@pytest.mark.parametrize("monitor_count", [1, 2])
def test_screen_outline_depends_on_monitor_count(tmp_path: Path, monitor_count: int) -> None:
    root = Path(__file__).resolve().parent.parent
    configuration = json.loads((root / "assets/default/config.json").read_text())
    configuration["monitors"] = {
        str(index): {"scaling_factor": 1, "is_primary": index == 0}
        for index in range(monitor_count)
    }
    configuration["palette"] = {
        configuration["state"]["theme"]: dict.fromkeys(
            ["background", "foreground", "neutral", "highlight", "notification", "warning"], "#111111"
        )
    }
    config_directory = tmp_path / ".config"
    config_directory.mkdir()
    (config_directory / "config.json").write_text(json.dumps(configuration))
    script = """
import runpy
import sys

config = runpy.run_path(sys.argv[1])
outlined = int(sys.argv[2]) > 1
assert len(config['screens']) == int(sys.argv[2])
for screen in config['screens']:
    assert bool(screen.top.border_width[0]) == outlined
    assert bool(screen.bottom.outline_size) == outlined
    for edge in (screen.left, screen.right):
        assert (edge is not None) == outlined
        if outlined:
            assert edge.size == config['FOCUS_BORDER_WIDTH']
            assert edge.background == config['FOCUS_BORDER_INACTIVE']
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(root / "configuration/qtile/config.py"), str(monitor_count)],
        env=os.environ | {"HOME": str(tmp_path), "PYTHONPATH": str(root / "configuration/qtile")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
