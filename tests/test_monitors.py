"""Monitor detection, and keeping ``config.json`` in step with a hotplug."""

import json
from pathlib import Path
from typing import Any

import pytest
import shared.state
from shared import monitors


class FakeMonitor:
    """What screeninfo returns, reduced to the attributes the geometry is derived from."""

    def __init__(self, name: str, pixels: tuple[int, int], millimetres: tuple[int, int],
                 is_primary: bool = False) -> None:
        self.name, self.is_primary = name, is_primary
        self.width, self.height = pixels
        self.width_mm, self.height_mm = millimetres


def configuration(monitors_block: dict[str, Any]) -> dict[str, Any]:
    return {"name": "default", "state": {"theme": "dark"}, "monitors": monitors_block}


def write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload))
    return path


def test_geometry_is_derived_from_the_physical_size(monkeypatch: pytest.MonkeyPatch) -> None:
    # 3840px across 598mm is 163 dpi; every scaled size in the bar is that over 100.
    monkeypatch.setattr(monitors.screeninfo, "get_monitors",
                        lambda: [FakeMonitor("HDMI-0", (3840, 2160), (598, 336), True)])
    detected = monitors.detect()["HDMI-0"]
    assert detected["width_dpi"] == 163
    assert detected["scaling_factor"] == pytest.approx(1.63)
    assert detected["is_primary"] is True


def test_a_monitor_reporting_no_physical_size_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    # Some virtual outputs report 0mm, which would divide by zero on the way to a DPI.
    monkeypatch.setattr(monitors.screeninfo, "get_monitors",
                        lambda: [FakeMonitor("VIRTUAL1", (1920, 1080), (0, 0))])
    assert monitors.detect() == {}


def test_a_failed_query_is_not_an_empty_desktop(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_error() -> None:
        raise monitors.screeninfo.ScreenInfoError("no display")
    monkeypatch.setattr(monitors.screeninfo, "get_monitors", raise_error)
    assert monitors.detect() == {}


def test_an_unchanged_layout_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # This is what stops the bar being rebuilt on every screen-change event that is not a plug.
    monkeypatch.setattr(monitors.screeninfo, "get_monitors",
                        lambda: [FakeMonitor("HDMI-0", (3840, 2160), (598, 336), True)])
    detected = monitors.detect()
    path = write(tmp_path / "config.json", configuration(detected))
    assert monitors.refresh(str(path)) is False


def test_a_new_display_is_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = write(tmp_path / "config.json", configuration({}))
    monkeypatch.setattr(monitors.screeninfo, "get_monitors",
                        lambda: [FakeMonitor("HDMI-0", (3840, 2160), (598, 336), True),
                                 FakeMonitor("DP-1", (1920, 1080), (527, 296))])
    assert monitors.refresh(str(path)) is True
    recorded = json.loads(path.read_text())["monitors"]
    assert sorted(recorded) == ["DP-1", "HDMI-0"]
    assert recorded["DP-1"]["scaling_factor"] > 0


# A failed query must never be mistaken for "every display was unplugged": writing that would
# leave the desktop with no geometry to scale from and nothing able to recover it.
def test_a_failed_query_never_erases_the_recorded_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = {"HDMI-0": {"scaling_factor": 1.63, "is_primary": True}}
    path = write(tmp_path / "config.json", configuration(original))
    monkeypatch.setattr(monitors, "detect", dict)
    assert monitors.refresh(str(path)) is False
    assert json.loads(path.read_text())["monitors"] == original


def test_refresh_on_a_missing_configuration_does_nothing(tmp_path: Path) -> None:
    assert monitors.refresh(str(tmp_path / "absent.json")) is False


def test_refresh_leaves_the_rest_of_the_configuration_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write(tmp_path / "config.json", configuration({}))
    monkeypatch.setattr(monitors.screeninfo, "get_monitors",
                        lambda: [FakeMonitor("HDMI-0", (3840, 2160), (598, 336), True)])
    monitors.refresh(str(path))
    written = shared.state.read_state(str(path))
    assert written["name"] == "default"
    assert written["state"]["theme"] == "dark"
