"""Audio capture failures must not block or crash the window manager."""

import json
import pathlib
import sys
import threading
from multiprocessing.connection import Connection
from typing import Any

import pytest
import shared.audio_capture
import widgets.audio
from widgets.audio import WidgetAudio

DEVICES = [
    {"name": "output only", "max_input_channels": 0, "default_samplerate": 48000.0},
    {"name": "default", "max_input_channels": 2, "default_samplerate": 48000.0},
    {"name": "dock input", "max_input_channels": 2, "default_samplerate": 48000.0},
]


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
def test_worker_selects_only_capture_capable_devices(
    monkeypatch: pytest.MonkeyPatch, device_id: int | None, direction: int, expected: int,
) -> None:
    frames = []

    class FakeStream:
        def __init__(self, **kwargs: Any) -> None:
            assert kwargs["device"] == expected
            self.active = True

        def __enter__(self) -> FakeStream:
            return self

        def __exit__(self, *args: Any) -> None:
            pass

    class FakeSounddevice:
        PortAudioError = RuntimeError
        InputStream = FakeStream

        @staticmethod
        def query_devices() -> list[dict[str, Any]]:
            return DEVICES

    class FakeConnection:
        def send(self, frame: tuple[int, list[float]]) -> None:
            frames.append(frame)
            raise BrokenPipeError

        def close(self) -> None:
            pass

    monkeypatch.setitem(sys.modules, "sounddevice", FakeSounddevice)
    shared.audio_capture.capture_worker(FakeConnection(), 16, device_id, direction)
    assert frames == [(expected, [0.0] * 16)]
