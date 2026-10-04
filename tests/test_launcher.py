"""Where rofi opens: on the screen qtile has focused, clear of its bar and its outline.

Measured on the running desktop before this: rofi took the monitor under the pointer
(its default, ``-m -5``), and the theme's averaged geometry -- 3840 pixels wide at a 62-pixel
offset -- covered the focused screen's 5-pixel side edges and the bottom four rows of its
66-pixel bar.
"""

import shared.launcher
from shared.launcher import Clearance


def _theme_str(command: list[str]) -> str:
    return command[command.index("-theme-str") + 1]


def test_rofi_is_sent_to_the_focused_screen_by_name() -> None:
    command = shared.launcher.rofi_command("run", "HDMI-1", Clearance(3840, 66, 5, 5))
    assert command[:3] == ["rofi", "-show", "run"]
    assert command[command.index("-m") + 1] == "HDMI-1"


def test_the_launcher_sits_inside_the_outline_and_below_the_bar() -> None:
    geometry = _theme_str(
        shared.launcher.rofi_command("run", "HDMI-1", Clearance(3840, 66, 5, 5))
    )
    assert "width: 3830px;" in geometry
    assert "y-offset: 66px;" in geometry
    assert "x-offset: 0px;" in geometry


def test_without_an_outline_the_launcher_spans_the_screen() -> None:
    geometry = _theme_str(shared.launcher.rofi_command("window", "HDMI-0", Clearance(2560, 40)))
    assert "width: 2560px;" in geometry
    assert "y-offset: 40px;" in geometry


# The north anchor centres the window; uneven edges would leave it off-centre by half the
# difference, which x-offset gives back.
def test_uneven_edges_are_evened_out() -> None:
    geometry = _theme_str(shared.launcher.rofi_command("run", "X", Clearance(1000, 10, 8, 2)))
    assert "width: 990px;" in geometry
    assert "x-offset: 3px;" in geometry


def test_an_unknown_output_leaves_the_monitor_to_rofi() -> None:
    assert "-m" not in shared.launcher.rofi_command("run", None, Clearance(1000, 10))


def test_a_script_mode_is_declared_for_rofi() -> None:
    command = shared.launcher.rofi_command("power", "HDMI-1", Clearance(1000, 10), "/x/power.sh")
    assert command[command.index("-modi") + 1] == "power:/x/power.sh"
    assert command[:3] == ["rofi", "-show", "power"]
