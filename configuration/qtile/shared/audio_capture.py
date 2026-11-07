"""Capture output monitors in a disposable process, never from microphone inputs."""

import ctypes
import json
import multiprocessing
import subprocess
import time
from multiprocessing.connection import Connection
from typing import Any

import numpy
import shared.spectrum

RETRY_SECONDS = 5.0
SAMPLE_RATE = 48000
FRAME_SAMPLES = 2048
SINK_CHECK_SECONDS = 1.0
PA_SAMPLE_FLOAT32LE = 5
PA_STREAM_RECORD = 2


def select_output(
    sinks: list[dict[str, Any]], default: str, device_id: int | None, direction: int
) -> dict[str, Any] | None:
    outputs = [
        sink for sink in sinks
        if isinstance(sink.get("index"), int)
        and isinstance(sink.get("name"), str)
        and isinstance(sink.get("monitor_source"), str)
        and sink["monitor_source"]
    ]
    selected = next((sink for sink in outputs if sink["index"] == device_id), None)
    if selected is None:
        selected = next((sink for sink in outputs if sink["name"] == default), None)
    if selected is None:
        return None
    return outputs[(outputs.index(selected) + direction) % len(outputs)]


class SampleSpec(ctypes.Structure):
    _fields_ = [("format", ctypes.c_int), ("rate", ctypes.c_uint32), ("channels", ctypes.c_uint8)]


class OutputMonitor:
    def __init__(self, source: str) -> None:
        self.library = ctypes.CDLL("libpulse-simple.so.0")
        self.library.pa_simple_new.restype = ctypes.c_void_p
        self.library.pa_simple_new.argtypes = [
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p,
            ctypes.POINTER(SampleSpec), ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int),
        ]
        self.library.pa_simple_read.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_int),
        ]
        self.library.pa_simple_free.argtypes = [ctypes.c_void_p]
        self.library.pa_simple_free.restype = None
        self.error = ctypes.c_int()
        spec = SampleSpec(PA_SAMPLE_FLOAT32LE, SAMPLE_RATE, 2)
        self.stream = self.library.pa_simple_new(
            None, b"qtile-audio-meter", PA_STREAM_RECORD, source.encode(), b"Output monitor",
            ctypes.byref(spec), None, None, ctypes.byref(self.error),
        )
        if not self.stream:
            raise OSError(f"cannot open output monitor: PulseAudio error {self.error.value}")
        self.buffer = ctypes.create_string_buffer(FRAME_SAMPLES * 2 * 4)

    def read(self) -> numpy.ndarray:
        if self.library.pa_simple_read(self.stream, self.buffer, len(self.buffer), ctypes.byref(self.error)) < 0:
            raise OSError(f"cannot read output monitor: PulseAudio error {self.error.value}")
        return numpy.frombuffer(self.buffer, dtype="<f4").reshape(-1, 2)

    def close(self) -> None:
        self.library.pa_simple_free(self.stream)


def default_output() -> str:
    return subprocess.run(
        ["pactl", "get-default-sink"], capture_output=True, text=True, check=True, timeout=2,
    ).stdout.strip()


def output_monitors() -> list[dict[str, Any]]:
    result = subprocess.run(
        ["pactl", "--format=json", "list", "sinks"], capture_output=True, text=True, check=True, timeout=2,
    )
    return json.loads(result.stdout)


def capture_worker(connection: Connection, num_bars: int, device_id: int | None, direction: int) -> None:
    """Publish spectrum levels from output monitors in a disposable process."""
    try:
        while True:
            default = default_output()
            output = select_output(output_monitors(), default, device_id, direction)
            if output is None:
                return
            monitor = OutputMonitor(output["monitor_source"])
            levels = numpy.zeros(num_bars)
            next_check = time.monotonic() + SINK_CHECK_SECONDS
            try:
                while True:
                    levels = 0.8 * levels + 0.2 * shared.spectrum.levels(monitor.read(), num_bars)
                    connection.send((output["index"], levels.tolist()))
                    if device_id is None and not direction and time.monotonic() >= next_check:
                        if default_output() != default:
                            break
                        next_check = time.monotonic() + SINK_CHECK_SECONDS
            finally:
                monitor.close()

    except (BrokenPipeError, EOFError, OSError, ValueError, subprocess.SubprocessError):
        return
    finally:
        connection.close()


class AudioCapture:
    """Nonblocking output-monitor capture with bounded retries after worker failures."""

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
        """Restart capture on a fresh output list without blocking Qtile."""
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
