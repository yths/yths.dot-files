"""Qtile widget: audio level visualisation.

Renders a bar-style level meter sampled live from ``sounddevice`` and overlays a
notification colour when the system mute state (read from the ``audio`` Redis stream)
is active. Implements ``libqtile.widget.base.InLoopPollText``.
"""

import json

import libqtile.widget.base
import libqtile.log_utils

try:
    import sounddevice
except ImportError:
    libqtile.log_utils.logger.warning("sounddevice module not found. Audio widget will not function.")
    sounddevice = None

import numpy


class WidgetAudio(libqtile.widget.base.InLoopPollText):
    def __init__(self, r, num_bars=16, device_id=31, notification_color="#ff0000", **config):
        libqtile.widget.base.InLoopPollText.__init__(self, **config)
        self.r = r

        self.notification_color = notification_color

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

        self.add_callbacks({"Button4": self.device_up, "Button5": self.device_down})
        self.decay = 0

    def device_up(self):
        self.decay = self.MAX_DECAY
        if self.device_id is not None:
            available_devices = len(sounddevice.query_devices())
            self.update_device((self.device_id + 1) % available_devices)

    def device_down(self):
        self.decay = self.MAX_DECAY
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
        data = self.r.xrevrange("audio", count=1)
        try:
            eid, payload = data[-1]
        except IndexError:
            return ""
        measurement = json.loads(payload.get(b"measurement").decode("utf-8"))


        output = f"<span letter_spacing='1024'>|{self.visualization}|</span>"

        if measurement["muted"] or measurement.get("volume", 0) <= 1:
            output = f"<span color='{self.notification_color}'>{output}</span>"
        alpha = numpy.clip(int(round(measurement.get("volume", 0) / 100 * 65536)), 6554, 65535)
        output = f"<span alpha='{alpha}'>{output}</span>"
        if self.decay > 0:
            self.decay -= 1
            self.decay = max(self.decay, 0)
            output = f"<span fgalpha='{max(self.decay * round(65535 / self.MAX_DECAY), 1)}'>{self.device_id}</span>" + output
        return output
    
    
    def finalize(self):
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        libqtile.widget.base.InLoopPollText.finalize(self)
