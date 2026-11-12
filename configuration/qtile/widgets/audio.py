"""Qtile widget: audio level visualisation.

Renders a bar-style level meter sampled live from ``sounddevice`` and overlays a
notification colour when the system mute state (read from the ``audio`` Redis stream)
is active. Implements ``libqtile.widget.base.InLoopPollText``.
"""

import time
from typing import Any

import libqtile.log_utils
import libqtile.widget.base
import numpy
import redis
import widgets._state
import widgets._stream

try:
    import sounddevice
except ImportError:
    libqtile.log_utils.logger.warning(
        "sounddevice module not found. Audio widget will not function."
    )
    sounddevice = None

#: What the PortAudio calls below can actually raise. ``PortAudioError`` covers a device
#: that has vanished or was never valid; the builtins cover a missing ``sounddevice``
#: module, an out-of-range index, and a device whose properties came back incomplete.
#: Named here rather than caught as a bare ``Exception`` so an unexpected failure still
#: surfaces instead of being silently swallowed by the bar.
AUDIO_ERRORS: tuple[type[BaseException], ...] = (
    (sounddevice.PortAudioError,) if sounddevice is not None else ()
) + (AttributeError, KeyError, OSError, TypeError, ValueError)


class WidgetAudio(libqtile.widget.base.InLoopPollText):
    def __init__(
        self,
        r: redis.Redis | None,
        num_bars: int = 16,
        device_id: int = 31,
        notification_color: str = "#ff0000",
        configuration_file_path: str | None = None,
        **config: Any,
    ) -> None:
        libqtile.widget.base.InLoopPollText.__init__(self, **config)
        self.r = r

        self.notification_color = notification_color
        self.configuration_file_path = (
            configuration_file_path
            if configuration_file_path is not None
            else widgets._state.CONFIGURATION_FILE_PATH
        )

        self.device_id = 0

        self.MAX_DECAY = 32

        self.NUM_BARS = num_bars
        try:
            self.device_id = max(device_id, 0)
            sounddevice.default.device = self.device_id
            self.device_properties = sounddevice.query_devices(self.device_id)
            self.stream = sounddevice.InputStream(
                channels=2,
                samplerate=self.device_properties['default_samplerate'],
                callback=self.callback_spectrum,
            )
            self.stream.start()
        except AUDIO_ERRORS:
            self.device_properties = None
            self.stream = None
        self.visualization = ' ' * self.NUM_BARS
        self.past_values = numpy.zeros(self.NUM_BARS, dtype=float)

        self.mode = self._load_mode()
        self.last_active_sink = None
        self._last_reenum = 0.0
        self.REENUM_INTERVAL = 5.0

        self.add_callbacks({
            "Button2": self.toggle_mode,
            "Button4": self.device_up,
            "Button5": self.device_down,
        })
        self.decay = 0

    def _load_mode(self) -> str:
        state = widgets._state.read_state(self.configuration_file_path).get("state", {})
        return state.get("audio_mode", "auto")

    def _save_mode(self, mode: str) -> None:
        widgets._state.update_state(self.configuration_file_path, audio_mode=mode)

    def _set_mode(self, mode: str) -> None:
        if mode == self.mode:
            return
        self.mode = mode
        self._save_mode(mode)

    def toggle_mode(self) -> None:
        self.decay = self.MAX_DECAY
        target = "manual" if self.mode == "auto" else "auto"
        self._set_mode(target)
        self.last_active_sink = None
        if target == "auto":
            # User-initiated refresh — bypass throttle so a freshly connected
            # bluetooth headset can be picked up immediately on middle-click.
            self._reenumerate_devices(force=True)

    def _auto_device_index(self) -> int | None:
        # The ALSA 'default' device is the alsa-pulse bridge — PipeWire/Pulse
        # routes whatever is currently playing through it, so capturing from
        # it tracks the active sink without per-sink mapping. The pulse-hostapi
        # entries for individual sinks (e.g. bluez_output monitors) often
        # don't deliver a usable input stream.
        if sounddevice is None:
            return None
        try:
            devices = sounddevice.query_devices()
        except AUDIO_ERRORS:
            return None
        for index, device in enumerate(devices):
            if device.get("name") == "default" and device.get("max_input_channels", 0) > 0:
                return index
        return None

    def _reenumerate_devices(self, force: bool = False) -> None:
        # PortAudio caches its device list at init; bluetooth headsets and
        # other hot-plugged sinks aren't visible until we terminate and
        # re-initialise. Throttled so a sink description that never resolves
        # doesn't cause a re-init storm.
        if sounddevice is None:
            return
        if not force and time.monotonic() - self._last_reenum < self.REENUM_INTERVAL:
            return
        self._last_reenum = time.monotonic()
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except AUDIO_ERRORS:
                libqtile.log_utils.logger.exception("stopping the audio stream failed")
            self.stream = None
        try:
            sounddevice._terminate()
            sounddevice._initialize()
        except AUDIO_ERRORS:
            libqtile.log_utils.logger.exception("sounddevice re-init failed")

    def device_up(self) -> None:
        self.decay = self.MAX_DECAY
        self._set_mode("manual")
        if self.device_id is not None:
            available_devices = len(sounddevice.query_devices())
            self.update_device((self.device_id + 1) % available_devices)

    def device_down(self) -> None:
        self.decay = self.MAX_DECAY
        self._set_mode("manual")
        if self.device_id is not None and self.device_id > 0:
            available_devices = len(sounddevice.query_devices())
            self.update_device((self.device_id - 1) % available_devices)

    def _close_stream(self) -> None:
        """Tear the input stream down, tolerating a device that has already gone away.

        Unguarded, a disconnected device raises PortAudioError out of ``poll()`` (via the
        auto-follow path) which permanently freezes the cell, and leaves ``self.stream``
        non-None so the reopen guard never fires and the stream is genuinely leaked.
        """
        if self.stream is None:
            return
        try:
            self.stream.stop()
            self.stream.close()
        except AUDIO_ERRORS:
            libqtile.log_utils.logger.exception("closing the audio stream failed")
        finally:
            self.stream = None

    def update_device(self, device_id: int) -> None:
        self.device_id = device_id
        self._close_stream()
        try:
            sounddevice.default.device = self.device_id
            self.device_properties = sounddevice.query_devices(self.device_id)
            self.stream = sounddevice.InputStream(
                channels=2,
                samplerate=self.device_properties['default_samplerate'],
                callback=self.callback_spectrum,
            )
            self.stream.start()
        except AUDIO_ERRORS:
            self.device_properties = None
            self.stream = None

    def compress_array(self, arr: numpy.ndarray, m: int) -> numpy.ndarray:
        n = len(arr)
        if m > n:
            raise ValueError("m must be less than or equal to n")
        # Calculate the size of each bin
        bins = numpy.linspace(0, n, m+1, dtype=int)
        return numpy.array([arr[bins[i]:bins[i+1]].sum() for i in range(m)])

    def callback_spectrum(
        self, in_data: numpy.ndarray, frame_count: int, time_info: Any, status: Any
    ) -> None:
        fft_data = numpy.abs(numpy.fft.fft(in_data - numpy.mean(in_data, axis=0), axis=0))
        spectrum = fft_data[:len(fft_data)//8, :]
        spectrum_left = spectrum[:, 0]
        spectrum_right = spectrum[:, 1]
        try:
            compressed_spectrum_left = self.compress_array(spectrum_left, self.NUM_BARS // 2)
            compressed_spectrum_right = self.compress_array(spectrum_right, self.NUM_BARS // 2)
            compressed_spectrum = numpy.concatenate((compressed_spectrum_left[::-1], compressed_spectrum_right))
            compressed_spectrum /= numpy.max([numpy.max(compressed_spectrum), 2])
            compressed_spectrum = 0.8 * self.past_values + 0.2 * compressed_spectrum
            self.past_values = compressed_spectrum
            discretized_spectrum = numpy.round(compressed_spectrum * 8).astype(int)
            # h runs 0..8 and 0 renders as a space, so the ladder starts at U+2580 to put
            # h=1 on ▁ and h=8 on █. Offsetting from U+2581 skipped ▁ entirely and landed
            # h=8 on ▉ (LEFT SEVEN EIGHTHS BLOCK), which fills horizontally, not vertically.
            unicode_blocks = [chr(0x2580 + h) if h > 0 else ' ' for h in discretized_spectrum]
            self.visualization = ''.join(unicode_blocks)
        except ValueError:
            pass

    def poll(self) -> str:
        if self.stream is None:
            try:
                sounddevice.default.device = self.device_id
                self.device_properties = sounddevice.query_devices(self.device_id)
                self.stream = sounddevice.InputStream(
                channels=2,
                samplerate=self.device_properties['default_samplerate'],
                callback=self.callback_spectrum,
            )
                self.stream.start()
            except AUDIO_ERRORS:
                self.device_properties = None
                self.stream = None

        measurement = widgets._stream.read_measurement(self.r, "audio")
        if measurement is None:
            return ""

        if self.mode == "auto":
            self.last_active_sink = measurement.get("active_sink")
            target = self._auto_device_index()
            if target is None:
                self._reenumerate_devices()
                target = self._auto_device_index()
            if target is not None and target != self.device_id:
                self.update_device(target)

        output = f"<span letter_spacing='1024'>|{self.visualization}|</span>"

        if measurement.get("muted") or measurement.get("volume", 0) <= 1:
            output = f"<span color='{self.notification_color}'>{output}</span>"
        alpha = numpy.clip(round(measurement.get("volume", 0) / 100 * 65536), 6554, 65535)
        output = f"<span alpha='{alpha}'>{output}</span>"
        if self.decay > 0:
            self.decay -= 1
            self.decay = max(self.decay, 0)
            mode_marker = "A" if self.mode == "auto" else "M"
            fgalpha = max(self.decay * round(65535 / self.MAX_DECAY), 1)
            output = (
                f"<span fgalpha='{fgalpha}'>{mode_marker}:{self.device_id}</span>"
                + output
            )
        return output


    def finalize(self) -> None:
        self._close_stream()
        libqtile.widget.base.InLoopPollText.finalize(self)
