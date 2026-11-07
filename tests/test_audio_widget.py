"""Audio capture failures must not block or crash the window manager."""

import json
import pathlib
import threading
from multiprocessing.connection import Connection
from typing import Any

import numpy
import preview_audio
import pytest
import shared.audio_capture
import widgets.audio
from widgets.audio import WidgetAudio

OUTPUTS = [
    {"index": 1, "name": "speakers", "monitor_source": "speakers.monitor"},
    {"index": 2, "name": "dock", "monitor_source": "dock.monitor"},
]


@pytest.mark.parametrize(
    ("device_id", "direction", "expected"), [(None, 0, 10), (20, 0, 20), (10, 1, 20), (10, -1, 20), (99, 0, 10)],
)
def test_output_selection_uses_only_sink_monitors(device_id: int | None, direction: int, expected: int) -> None:
    sinks = [
        {"index": 10, "name": "speakers", "monitor_source": "speakers.monitor"},
        {"index": 20, "name": "dock", "monitor_source": "dock.monitor"},
        {"index": 30, "name": "not-a-monitor"},
    ]
    assert shared.audio_capture.select_output(sinks, "speakers", device_id, direction)["index"] == expected
    assert shared.audio_capture.select_output(sinks, "missing", None, 0) is None


class FakeCapture:
    """Record capture requests without starting native audio."""

    def __init__(self, num_bars: int, device_id: int | None = None) -> None:
        self.num_bars = num_bars
        self.device_id = device_id
        self.reads = 0
        self.selections: list[tuple[int | None, int]] = []
        self.closed = False
        self.frame: tuple[int, list[float]] | None = None

    def read(self) -> tuple[int, list[float]] | None:
        self.reads += 1
        return self.frame

    def select(self, device_id: int | None = None, direction: int = 0) -> None:
        self.selections.append((device_id, direction))

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def capture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(widgets.audio.shared.audio_capture, "AudioCapture", FakeCapture)
    monkeypatch.setattr(widgets.audio.shared.stream, "read_measurement", lambda _r, _s: None)


def _widget(tmp_path: pathlib.Path, mode: str = "automatic", **config: Any) -> WidgetAudio:
    configuration = tmp_path / "config.json"
    configuration.write_text(json.dumps({"state": {"audio_mode": mode}}))
    return WidgetAudio(r=None, configuration_file_path=str(configuration), **config)


def test_building_the_widget_starts_no_capture(tmp_path: pathlib.Path, capture: None) -> None:
    widget = _widget(tmp_path)
    assert widget.capture.reads == 0


def test_automatic_mode_selects_default_in_the_worker(tmp_path: pathlib.Path, capture: None) -> None:
    widget = _widget(tmp_path, device_id=2)
    assert widget.capture.device_id is None
    widget.poll()
    assert widget.capture.reads == 1


def test_manual_mode_opens_the_chosen_device(tmp_path: pathlib.Path, capture: None) -> None:
    widget = _widget(tmp_path, mode="manual", device_id=2)
    assert widget.capture.device_id == 2


@pytest.mark.parametrize(("method", "direction"), [("device_up", 1), ("device_down", -1)])
def test_wheel_only_requests_a_worker_device_change(
    tmp_path: pathlib.Path, capture: None, method: str, direction: int,
) -> None:
    widget = _widget(tmp_path, device_id=1)
    getattr(widget, method)()
    assert widget.capture.selections == [(1, direction)]
    assert widget.capture.reads == 0
    assert widget.mode == "manual"


def test_automatic_toggle_discards_the_manual_device(tmp_path: pathlib.Path, capture: None) -> None:
    widget = _widget(tmp_path, mode="manual", device_id=2)
    widget.toggle_mode()
    assert widget.capture.selections == [(None, 0)]


def test_meter_renders_frames_from_the_worker(tmp_path: pathlib.Path, capture: None) -> None:
    widget = _widget(tmp_path)
    widget.capture.frame = (2, [0.5] * widget.NUM_BARS)
    widget.poll()
    assert widget.device_id == 2
    assert len(widget.visualization) == widget.NUM_BARS
    assert widget.visualization == widgets.audio.shared.spectrum.render(
        [0.5] * widget.NUM_BARS, widget.symbols["meter.ramp"],
    )


def test_meter_clears_a_stale_capture_frame(
    tmp_path: pathlib.Path, capture: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    widget = _widget(tmp_path)
    widget.visualization = "x" * widget.NUM_BARS
    widget.last_frame_at = 10.0
    monkeypatch.setattr(widgets.audio.time, "monotonic", lambda: 11.0)
    widget.poll()
    assert widget.visualization == shared.spectrum.SILENCE * widget.NUM_BARS


def test_finalize_stops_the_worker(
    tmp_path: pathlib.Path, capture: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(widgets.audio.libqtile.widget.base.InLoopPollText, "finalize", lambda _self: None)
    widget = _widget(tmp_path)
    widget.finalize()
    assert widget.capture.closed


def _waiting_worker(connection: Connection, num_bars: int, device_id: int | None, direction: int) -> None:
    connection.send((1, [0.5] * num_bars))
    threading.Event().wait(timeout=10)


def test_native_worker_death_is_contained_and_capture_recovers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shared.audio_capture, "capture_worker", _waiting_worker)
    capture = shared.audio_capture.AudioCapture(16)
    try:
        capture.read()
        assert capture._connection.poll(timeout=5)
        assert capture.read() == (1, [0.5] * 16)
        process = capture._process
        process.kill()
        process.join(timeout=5)
        assert not process.is_alive()
        assert capture.read() is None
        assert capture._process is None
        assert capture.read() is None
        assert capture._process is None, "a crashed device must not cause a restart storm"
        capture._next_start = 0
        capture.read()
        assert capture._connection.poll(timeout=5)
        assert capture.read() == (1, [0.5] * 16)
    finally:
        capture.close()


@pytest.mark.parametrize(
    ("device_id", "direction", "expected"), [(None, 0, 1), (2, 0, 2), (1, 1, 2), (1, -1, 2)],
)
def test_worker_captures_only_the_selected_output_monitor(
    monkeypatch: pytest.MonkeyPatch, device_id: int | None, direction: int, expected: int,
) -> None:
    frames = []
    sources = []

    class FakeMonitor:
        def __init__(self, source: str) -> None:
            sources.append(source)

        def read(self) -> numpy.ndarray:
            return numpy.zeros((2048, 2))

        def close(self) -> None:
            pass

    class FakeConnection:
        def send(self, frame: tuple[int, list[float]]) -> None:
            frames.append(frame)
            raise BrokenPipeError

        def close(self) -> None:
            pass

    monkeypatch.setattr(shared.audio_capture, "default_output", lambda: "speakers")
    monkeypatch.setattr(shared.audio_capture, "output_monitors", lambda: OUTPUTS)
    monkeypatch.setattr(shared.audio_capture, "OutputMonitor", FakeMonitor)
    shared.audio_capture.capture_worker(FakeConnection(), 16, device_id, direction)
    assert frames == [(expected, [0.0] * 16)]
    assert sources == [next(output["monitor_source"] for output in OUTPUTS if output["index"] == expected)]


def test_worker_follows_default_output_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    defaults = iter(["speakers", "dock", "dock"])
    sources = []
    closed = []
    frames = []

    class FakeMonitor:
        def __init__(self, source: str) -> None:
            self.source = source
            sources.append(source)

        def read(self) -> numpy.ndarray:
            return numpy.zeros((2048, 2))

        def close(self) -> None:
            closed.append(self.source)

    class FakeConnection:
        def send(self, frame: tuple[int, list[float]]) -> None:
            frames.append(frame)
            if len(frames) == 2:
                raise BrokenPipeError

        def close(self) -> None:
            pass

    monkeypatch.setattr(shared.audio_capture, "default_output", lambda: next(defaults))
    monkeypatch.setattr(shared.audio_capture, "output_monitors", lambda: OUTPUTS)
    monkeypatch.setattr(shared.audio_capture, "OutputMonitor", FakeMonitor)
    monkeypatch.setattr(shared.audio_capture, "SINK_CHECK_SECONDS", 0)
    shared.audio_capture.capture_worker(FakeConnection(), 16, None, 0)
    assert sources == ["speakers.monitor", "dock.monitor"]
    assert closed == sources
    assert [frame[0] for frame in frames] == [1, 2]


def test_worker_reports_output_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    frames = []
    tone = numpy.sin(2 * numpy.pi * 440 * numpy.arange(2048) / 48000) * 0.1

    class FakeMonitor:
        def __init__(self, source: str) -> None:
            assert source == "speakers.monitor"

        def read(self) -> numpy.ndarray:
            return numpy.column_stack((tone, tone))

        def close(self) -> None:
            pass

    class FakeConnection:
        def send(self, frame: tuple[int, list[float]]) -> None:
            frames.append(frame)
            raise BrokenPipeError

        def close(self) -> None:
            pass

    monkeypatch.setattr(shared.audio_capture, "default_output", lambda: "speakers")
    monkeypatch.setattr(shared.audio_capture, "output_monitors", lambda: OUTPUTS)
    monkeypatch.setattr(shared.audio_capture, "OutputMonitor", FakeMonitor)
    shared.audio_capture.capture_worker(FakeConnection(), 16, None, 0)
    assert frames[0][0] == 1
    assert max(frames[0][1]) > 0


@pytest.mark.parametrize("device", [2, "dock"])
def test_preview_selects_output_monitor(monkeypatch: pytest.MonkeyPatch, device: int | str) -> None:
    sources = []

    class FakeMonitor:
        def __init__(self, source: str) -> None:
            sources.append(source)

        def read(self) -> numpy.ndarray:
            raise KeyboardInterrupt

        def close(self) -> None:
            pass

    monkeypatch.setattr(shared.audio_capture, "default_output", lambda: "speakers")
    monkeypatch.setattr(shared.audio_capture, "output_monitors", lambda: OUTPUTS)
    monkeypatch.setattr(shared.audio_capture, "OutputMonitor", FakeMonitor)
    assert preview_audio.preview(device, 16) == 0
    assert sources == ["dock.monitor"]
