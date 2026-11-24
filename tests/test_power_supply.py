"""The battery cell: compact by default, the detail ``tlp-stat -b`` would show on demand."""

from typing import Any

import pytest
import symbols
import widgets.claude_usage
from shared.hover import HoverExpand
from widgets.power_supply import WidgetPowerSupply

#: Two ThinkPad batteries as yths.backend-service publishes them, BAT1 the one in use.
MEASUREMENT: dict[str, Any] = {
    "grid": False,
    "batteries": {
        "BAT0": {
            "capacity": "84", "status": "Not charging",
            "energy_now_wh": 19.83, "energy_full_wh": 23.47, "health": 100.4,
            "cycle_count": 4, "power_w": 0.0, "seconds_left": None,
            "charge_start_threshold": 15, "charge_end_threshold": 85,
        },
        "BAT1": {
            "capacity": "62", "status": "Discharging",
            "energy_now_wh": 45.1, "energy_full_wh": 72.75, "health": 101.0,
            "cycle_count": 9, "power_w": 9.02, "seconds_left": 18000,
            "charge_start_threshold": 15, "charge_end_threshold": 85,
        },
    },
    "tlp": {"enabled": True, "profile": "balanced/BAL", "power_source": "battery"},
}


def cell(measurement: dict[str, Any] | None, expanded: bool = False) -> WidgetPowerSupply:
    widget = WidgetPowerSupply.__new__(WidgetPowerSupply)
    widget.symbols, widget.strings = symbols.SYMBOLS, symbols.STRINGS
    widget.highlight_color = "#ff0000"
    widget.measurement = measurement
    widget.expanded = expanded
    return widget


def test_the_compact_cell_is_one_glyph_per_battery() -> None:
    discharging = symbols.SYMBOLS["battery.discharging"]
    # The trailing space is room for the last glyph's ink, which overruns its advance. The
    # cell takes the bar's default padding, so the space on its two sides matches its
    # neighbours'; a wider padding in config.py left the cell before it off-centre.
    assert cell(MEASUREMENT)._render() == f"{discharging[8]} {discharging[6]} "
    assert cell({**MEASUREMENT, "grid": True})._render().startswith(symbols.SYMBOLS["battery.grid"])


def test_a_cell_with_nothing_to_show_is_empty_not_a_lone_space() -> None:
    assert cell({"grid": False, "batteries": {}})._render() == ""


def test_hovering_adds_charge_draw_time_left_and_profile() -> None:
    discharging = symbols.SYMBOLS["battery.discharging"]
    assert cell(MEASUREMENT, expanded=True)._render() == (
        f"{discharging[8]} 84% {discharging[6]} 62% 9.0 W 5h00 left BAL"
    )


def test_charging_counts_down_to_the_threshold() -> None:
    charging = {**MEASUREMENT, "grid": True, "batteries": {
        "BAT0": {**MEASUREMENT["batteries"]["BAT0"], "status": "Charging", "seconds_left": 1800},
    }}
    assert cell(charging, expanded=True)._render().endswith("30m to threshold BAL")


def test_the_notification_carries_what_tlp_stat_b_shows() -> None:
    summary = cell(MEASUREMENT)._summary()
    assert "BAT0 84% · 19.8/23.5 Wh · health 100% · 4 cycles · charges 15-85%" in summary
    assert "BAT1 62%" in summary
    assert summary.endswith("9.0 W   5h00 left   TLP balanced")


def test_an_older_backend_still_renders() -> None:
    """Capacity and status are all a backend from before the detail fields publishes."""
    old = {"grid": True, "batteries": {"BAT0": {"capacity": "84", "status": "Full"}}}
    discharging = symbols.SYMBOLS["battery.discharging"]
    assert cell(old, expanded=True)._render() == f"{symbols.SYMBOLS['battery.grid']} {discharging[8]} 84%"
    assert cell(old)._summary() == "BAT0 84%"


@pytest.mark.parametrize("measurement", [None, {"grid": True, "batteries": "junk"}])
def test_no_or_malformed_data_is_said_rather_than_raised(measurement: dict | None) -> None:
    assert cell(measurement)._summary() == symbols.STRINGS["battery.no_data"]


def test_both_hover_cells_share_one_implementation() -> None:
    for widget in (WidgetPowerSupply, widgets.claude_usage.WidgetClaudeUsage):
        assert issubclass(widget, HoverExpand)
        assert "_pointer_is_on_me" not in widget.__dict__


def test_hover_redraws_from_the_current_state(monkeypatch: pytest.MonkeyPatch) -> None:
    drawn: list[str] = []
    monkeypatch.setattr(
        "libqtile.widget.base.BackgroundPoll.update", lambda _self, text: drawn.append(text),
    )
    widget = cell(MEASUREMENT)
    widget.mouse_enter(0, 0)
    widget.mouse_leave(0, 0)
    assert "84%" in drawn[0] and "84%" not in drawn[1]
