"""Qtile widget: audio level visualisation.

Renders a bar-style level meter sampled live from ``sounddevice`` and overlays a
notification colour when the system mute state (read from the ``audio`` Redis stream)
is active. Implements ``libqtile.widget.base.InLoopPollText``.
"""

import json
import os
import time

import libqtile.widget.base
import libqtile.log_utils
import redis.exceptions

try:
    import sounddevice
except ImportError:
    libqtile.log_utils.logger.warning("sounddevice module not found. Audio widget will not function.")
    sounddevice = None

import numpy


class WidgetAudio(libqtile.widget.base.InLoopPollText):
    def __init__(
        self,
        r,
        num_bars=16,
        device_id=31,
        notification_color="#ff0000",
        configuration_file_path=os.path.expanduser(
            os.path.join("~", ".config", "config.json")
        ),
        **config,
    ):
        libqtile.widget.base.InLoopPollText.__init__(self, **config)
        self.r = r

        self.notification_color = notification_color
        self.configuration_file_path = configuration_file_path

        self.device_id = 0

        self.MAX_DECAY = 32

        self.NUM_BARS = num_bars
        try:
            self.device_id = max(device_id, 0)
            sounddevice.default.device = self.device_id
            self.device_properties = sounddevice.query_devices(self.device_id)
            self.stream = sounddevice.InputStream(channels=2, samplerate=self.device_properties['default_samplerate'], callback=self.callback_spectrum)
            self.stream.start()
        except Exception:
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

    def _load_mode(self):
        try:
            with open(self.configuration_file_path, "r") as f:
                return json.load(f).get("state", {}).get("audio_mode", "auto")
        except (OSError, ValueError):
            return "auto"

    def _save_mode(self, mode):
        try:
            with open(self.configuration_file_path, "r") as f:
                configuration = json.load(f)
        except (OSError, ValueError):
            return
        configuration.setdefault("state", {})["audio_mode"] = mode
        try:
            with open(self.configuration_file_path, "w") as f:
                json.dump(configuration, f, indent=4)
        except OSError:
            pass

    def _set_mode(self, mode):
        if mode == self.mode:
            return
        self.mode = mode
        self._save_mode(mode)

    def toggle_mode(self):
        self.decay = self.MAX_DECAY
        target = "manual" if self.mode == "auto" else "auto"
        self._set_mode(target)
        self.last_active_sink = None
        if target == "auto":
            # User-initiated refresh — bypass throttle so a freshly connected
            # bluetooth headset can be picked up immediately on middle-click.
            self._reenumerate_devices(force=True)

    def _auto_device_index(self):
        # The ALSA 'default' device is the alsa-pulse bridge — PipeWire/Pulse
        # routes whatever is currently playing through it, so capturing from
        # it tracks the active sink without per-sink mapping. The pulse-hostapi
        # entries for individual sinks (e.g. bluez_output monitors) often
        # don't deliver a usable input stream.
        if sounddevice is None:
            return None
        try:
            devices = sounddevice.query_devices()
        except Exception:
            return None
        for index, device in enumerate(devices):
            if device.get("name") == "default" and device.get("max_input_channels", 0) > 0:
                return index
        return None

    def _reenumerate_devices(self, force=False):
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
            except Exception:
                pass
            self.stream = None
        try:
            sounddevice._terminate()
            sounddevice._initialize()
        except Exception:
            libqtile.log_utils.logger.exception("sounddevice re-init failed")

    def device_up(self):
        self.decay = self.MAX_DECAY
        self._set_mode("manual")
        if self.device_id is not None:
            available_devices = len(sounddevice.query_devices())
            self.update_device((self.device_id + 1) % available_devices)

    def device_down(self):
        self.decay = self.MAX_DECAY
        self._set_mode("manual")
        if self.device_id is not None and self.device_id > 0:
            available_devices = len(sounddevice.query_devices())
            self.update_device((self.device_id - 1) % available_devices)

    def update_device(self, device_id):
        self.device_id = device_id
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
        try:
            sounddevice.default.device = self.device_id
            self.device_properties = sounddevice.query_devices(self.device_id)
            self.stream = sounddevice.InputStream(channels=2, samplerate=self.device_properties['default_samplerate'], callback=self.callback_spectrum)
            self.stream.start()
        except Exception:
            self.device_properties = None
            self.stream = None

    def compress_array(self, arr, m):
        n = len(arr)
        if m > n:
            raise ValueError("m must be less than or equal to n")
        # Calculate the size of each bin
        bins = numpy.linspace(0, n, m+1, dtype=int)
        compressed = numpy.array([arr[bins[i]:bins[i+1]].sum() for i in range(m)])
        return compressed

    def callback_spectrum(self, in_data, frame_count, time_info, status):
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
            unicode_blocks = [chr(0x2581 + h) if h > 0 else ' ' for h in discretized_spectrum]
            self.visualization = ''.join(unicode_blocks)
        except ValueError:
            pass

    def poll(self):
        if self.stream is None:
            try:
                sounddevice.default.device = self.device_id
                self.device_properties = sounddevice.query_devices(self.device_id)
                self.stream = sounddevice.InputStream(channels=2, samplerate=self.device_properties['default_samplerate'], callback=self.callback_spectrum)
                self.stream.start()
            except Exception:
                self.device_properties = None
                self.stream = None

        if self.r is None:
            return ""
        try:
            data = self.r.xrevrange("audio", count=1)
            eid, payload = data[-1]
            measurement = json.loads(payload.get(b"measurement").decode("utf-8"))
        except (IndexError, KeyError, AttributeError, TypeError, ValueError, json.JSONDecodeError, redis.exceptions.RedisError):
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

        if measurement["muted"] or measurement.get("volume", 0) <= 1:
            output = f"<span color='{self.notification_color}'>{output}</span>"
        alpha = numpy.clip(int(round(measurement.get("volume", 0) / 100 * 65536)), 6554, 65535)
        output = f"<span alpha='{alpha}'>{output}</span>"
        if self.decay > 0:
            self.decay -= 1
            self.decay = max(self.decay, 0)
            mode_marker = "A" if self.mode == "auto" else "M"
            output = f"<span fgalpha='{max(self.decay * round(65535 / self.MAX_DECAY), 1)}'>{mode_marker}:{self.device_id}</span>" + output
        return output
    
    
    def finalize(self):
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        libqtile.widget.base.InLoopPollText.finalize(self)
