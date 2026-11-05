"""Isolate PortAudio capture from Qtile so a device failure cannot end the session."""

import multiprocessing
import time
from multiprocessing.connection import Connection
from typing import Any

import numpy
import shared.spectrum

RETRY_SECONDS = 5.0
FRAME_SECONDS = 0.1


def capture_worker(connection: Connection, num_bars: int, device_id: int | None, direction: int) -> None:
    """Publish spectrum levels from a disposable process that alone loads PortAudio."""
    import sounddevice

    try:
        devices = sounddevice.query_devices()
        inputs = [index for index, device in enumerate(devices) if device["max_input_channels"] > 0]
        if not inputs:
            return
        if device_id not in inputs:
            device_id = next((index for index in inputs if devices[index]["name"] == "default"), inputs[0])
        if direction:
            device_id = inputs[(inputs.index(device_id) + direction) % len(inputs)]
        properties = devices[device_id]
        levels = numpy.zeros(num_bars)

        def capture(indata: Any, frames: int, timestamp: Any, status: Any) -> None:
            nonlocal levels
            try:
                levels = 0.8 * levels + 0.2 * shared.spectrum.levels(indata, num_bars)
            except ValueError:
                return

        with sounddevice.InputStream(
            device=device_id, channels=min(2, properties["max_input_channels"]),
            samplerate=properties["default_samplerate"], callback=capture,
        ) as stream:
            while stream.active:
                connection.send((device_id, levels.tolist()))
                time.sleep(FRAME_SECONDS)
    except (sounddevice.PortAudioError, BrokenPipeError, EOFError, OSError, ValueError):
        return
    finally:
        connection.close()


class AudioCapture:
    """Nonblocking capture client with bounded retries after native worker crashes."""

    def __init__(self, num_bars: int, device_id: int | None = None) -> None:
        self.num_bars = num_bars
        self.device_id = device_id
        self.direction = 0
        self._context = multiprocessing.get_context("spawn")
        self._process = None
        self._connection: Connection | None = None
        self._next_start = 0.0

    def read(self) -> tuple[int, list[float]] | None:
        """Read available frames without waiting for capture or device enumeration."""
        if self._process is not None and not self._process.is_alive():
            self.close()
            self._next_start = time.monotonic() + RETRY_SECONDS
        if self._process is None:
            if time.monotonic() < self._next_start:
                return None
            receiver, sender = self._context.Pipe(duplex=False)
            self._process = self._context.Process(
                target=capture_worker, args=(sender, self.num_bars, self.device_id, self.direction), daemon=True,
            )
            try:
                self._process.start()
            except (OSError, RuntimeError):
                receiver.close()
                self._process = None
                self._next_start = time.monotonic() + RETRY_SECONDS
                return None
            finally:
                sender.close()
            self._connection = receiver
        latest = None
        try:
            while self._connection is not None and self._connection.poll():
                latest = self._connection.recv()
        except (EOFError, OSError):
            self.close()
            self._next_start = time.monotonic() + RETRY_SECONDS
        if latest is not None:
            if self.device_id is not None or self.direction:
                self.device_id = latest[0]
            self.direction = 0
        return latest

    def select(self, device_id: int | None = None, direction: int = 0) -> None:
        """Restart capture on a fresh device list, without querying PortAudio in Qtile."""
        self.close()
        self.device_id = device_id
        self.direction = direction
        self._next_start = 0.0

    def close(self) -> None:
        """Stop the worker without calling native stream teardown inside Qtile."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        if self._process is not None:
            if self._process.is_alive():
                self._process.terminate()
            self._process.join(timeout=0.1)
            if not self._process.is_alive():
                self._process.close()
            self._process = None
