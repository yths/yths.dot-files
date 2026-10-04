"""When the audio meter opens its capture stream, and on which device.

A config reload crashed qtile -- and so ended the session -- with PipeWire's JACK thread
calling a freed PortAudio callback. Every audio widget opened a stream in ``__init__``, the
moment config.py was evaluated, on the old default of device 31, a JACK input; automatic
mode then closed it within a second to move to ``default``. Two of those per config load,
one per screen. These tests hold the two properties that remove the window: building the
widget opens nothing, and the first poll opens one stream, on the device it keeps.
"""

import json
import pathlib

import pytest
import widgets.audio
from widgets.audio import WidgetAudio

DEVICES = [
    {"name": "hw", "max_input_channels": 2, "default_samplerate": 48000.0},
    {"name": "default", "max_input_channels": 2, "default_samplerate": 48000.0},
    {"name": "jack input", "max_input_channels": 2, "default_samplerate": 48000.0},
]


class FakeSounddevice:
    """The parts of ``sounddevice`` the widget uses, recording every stream event."""

    def __init__(self) -> None:
        self.events: list[tuple[str, int]] = []
        fake = self

        class Default:
            device = None

        class InputStream:
            def __init__(self, **_kwargs: object) -> None:
                self.device = fake.default.device
                fake.events.append(("open", self.device))

            def start(self) -> None:
                fake.events.append(("start", self.device))

            def stop(self) -> None:
                fake.events.append(("stop", self.device))

            def close(self) -> None:
                fake.events.append(("close", self.device))

        self.default = Default()
        self.InputStream = InputStream

    def query_devices(self, index: int | None = None) -> object:
        return DEVICES if index is None else DEVICES[index]

    def _terminate(self) -> None:
        self.events.append(("terminate", -1))

    def _initialize(self) -> None:
        pass


@pytest.fixture
def sounddevice(monkeypatch: pytest.MonkeyPatch) -> FakeSounddevice:
    fake = FakeSounddevice()
    monkeypatch.setattr(widgets.audio, "sounddevice", fake)
    monkeypatch.setattr(widgets.audio.shared.stream, "read_measurement", lambda _r, _s: None)
    return fake


def _widget(tmp_path: pathlib.Path, mode: str = "automatic", **config: object) -> WidgetAudio:
    configuration = tmp_path / "config.json"
    configuration.write_text(json.dumps({"state": {"audio_mode": mode}}))
    return WidgetAudio(r=None, configuration_file_path=str(configuration), **config)


def test_building_the_widget_opens_no_stream(
    tmp_path: pathlib.Path, sounddevice: FakeSounddevice
) -> None:
    _widget(tmp_path)
    assert sounddevice.events == []


def test_the_first_poll_opens_one_stream_directly_on_default(
    tmp_path: pathlib.Path, sounddevice: FakeSounddevice
) -> None:
    widget = _widget(tmp_path)
    widget.poll()
    assert sounddevice.events == [("open", 1), ("start", 1)], "no detour through another device"
    widget.poll()
    assert sounddevice.events == [("open", 1), ("start", 1)], "and nothing more once it is there"


def test_manual_mode_opens_the_chosen_device(
    tmp_path: pathlib.Path, sounddevice: FakeSounddevice
) -> None:
    widget = _widget(tmp_path, mode="manual", device_id=2)
    widget.poll()
    assert sounddevice.events == [("open", 2), ("start", 2)]


def test_finalize_stops_and_closes_the_stream(
    tmp_path: pathlib.Path, sounddevice: FakeSounddevice, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The base class tears down a drawer that only a widget placed in a bar has.
    monkeypatch.setattr(
        widgets.audio.libqtile.widget.base.InLoopPollText, "finalize", lambda _self: None
    )
    widget = _widget(tmp_path)
    widget.poll()
    widget.finalize()
    assert sounddevice.events[-2:] == [("stop", 1), ("close", 1)]
    assert widget.stream is None
