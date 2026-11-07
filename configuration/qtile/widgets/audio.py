"""Qtile widget: audio level visualisation.

Renders a bar-style level meter sampled by an isolated capture process and overlays a
notification colour when the system mute state (read from the ``audio`` Redis stream)
is active. Implements ``libqtile.widget.base.InLoopPollText``.
"""

import time
from typing import Any

import libqtile.widget.base
import numpy
import redis
import shared.audio_capture
import shared.spectrum
import shared.state
import shared.stream
import symbols as vocabulary


class WidgetAudio(libqtile.widget.base.InLoopPollText):
    def __init__(
        self,
        r: redis.Redis | None,
        num_bars: int = 16,
        device_id: int | None = None,
        notification_color: str = "#ff0000",
        configuration_file_path: str | None = None,
        symbols: dict[str, Any] | None = None,
        **config: Any,
    ) -> None:
        libqtile.widget.base.InLoopPollText.__init__(self, **config)
        self.r = r

        self.notification_color = notification_color
        self.configuration_file_path = (
            configuration_file_path
            if configuration_file_path is not None
            else shared.state.CONFIGURATION_FILE_PATH
        )

        self.device_id = max(device_id, 0) if device_id is not None else None

        self.MAX_DECAY = 32

        self.NUM_BARS = num_bars
        self.visualization = shared.spectrum.SILENCE * self.NUM_BARS
        self.last_frame_at = time.monotonic()
        #: The active vocabulary, passed down from config.py the same way the colours are.
        #: Defaults to ASCII so a widget built without one still draws a meter.
        self.symbols = symbols or vocabulary.SYMBOLS
        self.mode = self._load_mode()
        self.last_active_sink = None
        self.capture = shared.audio_capture.AudioCapture(
            self.NUM_BARS, self.device_id if self.mode == "manual" else None,
        )

        self.add_callbacks({
            "Button2": self.toggle_mode,
            "Button4": self.device_up,
            "Button5": self.device_down,
        })
        self.decay = 0

    def _load_mode(self) -> str:
        state = shared.state.read_state(self.configuration_file_path).get("state", {})
        return state.get("audio_mode", "automatic")

    def _save_mode(self, mode: str) -> None:
        shared.state.update_state(self.configuration_file_path, audio_mode=mode)

    def _set_mode(self, mode: str) -> None:
        if mode == self.mode:
            return
        self.mode = mode
        self._save_mode(mode)

    def toggle_mode(self) -> None:
        self.decay = self.MAX_DECAY
        target = "manual" if self.mode == "automatic" else "automatic"
        self._set_mode(target)
        self.last_active_sink = None
        self.capture.select(self.device_id if target == "manual" else None)

    def device_up(self) -> None:
        self.decay = self.MAX_DECAY
        self._set_mode("manual")
        self.capture.select(self.device_id, direction=1)

    def device_down(self) -> None:
        self.decay = self.MAX_DECAY
        self._set_mode("manual")
        self.capture.select(self.device_id, direction=-1)

    def poll(self) -> str:
        frame = self.capture.read()
        if frame is not None:
            self.device_id, levels = frame
            self.visualization = shared.spectrum.render(levels, self.symbols["meter.ramp"])
            self.last_frame_at = time.monotonic()
        elif time.monotonic() - self.last_frame_at >= 1.0:
            self.visualization = shared.spectrum.SILENCE * self.NUM_BARS

        measurement = shared.stream.read_measurement(self.r, "audio")
        if measurement is None:
            return ""

        if self.mode == "automatic":
            self.last_active_sink = measurement.get("active_sink")

        output = f"<span letter_spacing='1024'>|{self.visualization}|</span>"

        if measurement.get("muted") or measurement.get("volume", 0) <= 1:
            output = f"<span color='{self.notification_color}'>{output}</span>"
        alpha = numpy.clip(round(measurement.get("volume", 0) / 100 * 65536), 6554, 65535)
        output = f"<span alpha='{alpha}'>{output}</span>"
        if self.decay > 0:
            self.decay -= 1
            self.decay = max(self.decay, 0)
            mode_marker = "A" if self.mode == "automatic" else "M"
            fgalpha = max(self.decay * round(65535 / self.MAX_DECAY), 1)
            output = (
                f"<span fgalpha='{fgalpha}'>{mode_marker}:{self.device_id}</span>"
                + output
            )
        return output


    def finalize(self) -> None:
        self.capture.close()
        libqtile.widget.base.InLoopPollText.finalize(self)
