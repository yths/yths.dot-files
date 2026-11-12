"""Preview the qtile audio meter in a terminal and pick a capture device.

The bar's level meter is eight characters of block glyphs in a status bar, which makes it a
poor place to work out why it is flat: is the device wrong, is nothing playing, or is the
rendering broken? This draws the same meter full-width in a terminal, from
``configuration/qtile/shared/spectrum.py`` -- the module the widget itself renders through --
so what appears here is what the bar will draw.

Usage::

    python helper/preview_audio.py --list          # capture devices, with their indices
    python helper/preview_audio.py                 # preview the system default input
    python helper/preview_audio.py --device 31     # preview a specific device
    python helper/preview_audio.py --device pulse  # ... or the first whose name matches

Pass the chosen index to ``WidgetAudio(device_id=...)`` in ``configuration/qtile/config.py``.
"""

import argparse
import os
import sys
import time

import numpy
import sounddevice

#: This file's repository, resolved through any symlink used to invoke it.
_REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# The qtile configuration directory is on sys.path when qtile loads the widgets; it is not
# when this runs as a script. Adding it is what lets the preview share the widget's own
# rendering rather than carrying a copy that drifts out of step -- which is exactly what
# the harness this replaced had done.
sys.path.insert(0, os.path.join(_REPOSITORY_ROOT, "configuration", "qtile"))

import shared.spectrum  # noqa: E402

#: Matches the widget's default, so the preview shows the same number of bars as the bar.
DEFAULT_NUM_BARS = 16


def list_devices() -> int:
    """Print every device that can be captured from, with the index the widget expects."""
    try:
        devices = sounddevice.query_devices()
    except sounddevice.PortAudioError as error:
        print(f"PortAudio is unavailable: {error}", file=sys.stderr)
        return 1
    default_input = sounddevice.default.device[0]
    for index, device in enumerate(devices):
        if device["max_input_channels"] < 2:
            continue
        marker = "*" if index == default_input else " "
        rate = round(device["default_samplerate"])
        print(f"{marker} {index:>3}  {device['name']}  ({rate} Hz)")
    print("\n* is the system default input. Devices with fewer than 2 channels are omitted.")
    return 0


def preview(device: str | int | None, num_bars: int) -> int:
    """Draw the meter until interrupted. Returns a process exit status."""
    try:
        properties = sounddevice.query_devices(device, kind="input")
    except (sounddevice.PortAudioError, ValueError) as error:
        print(f"cannot open device {device!r}: {error}", file=sys.stderr)
        return 1

    print(f"Capturing from {properties['name']} — Ctrl-C to stop.")
    meter = shared.spectrum.SILENCE * num_bars

    def draw(indata: numpy.ndarray, frames: int, timestamp: object, status: object) -> None:
        nonlocal meter
        if status:
            print(f"\n{status}", file=sys.stderr)
        try:
            meter = shared.spectrum.render(shared.spectrum.levels(indata, num_bars))
        except ValueError:
            # Capture too short to fill the bars; keep the previous frame on screen.
            return

    try:
        with sounddevice.InputStream(
            device=device,
            channels=2,
            samplerate=properties["default_samplerate"],
            callback=draw,
        ):
            while True:
                print(f"\r|{meter}|", end="", flush=True)
                time.sleep(0.05)
    except KeyboardInterrupt:
        print()
        return 0
    except sounddevice.PortAudioError as error:
        print(f"\ncapture failed: {error}", file=sys.stderr)
        return 1


def parse_device(value: str) -> str | int:
    """A device is an index if it looks like one, otherwise a name to match on."""
    return int(value) if value.lstrip("-").isdigit() else value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--list",
        action="store_true",
        help="list capture devices and their indices, then exit",
    )
    parser.add_argument(
        "--device",
        type=parse_device,
        default=None,
        help="device index or name substring (default: the system default input)",
    )
    parser.add_argument(
        "--bars",
        type=int,
        default=DEFAULT_NUM_BARS,
        help=f"number of bars to draw (default: {DEFAULT_NUM_BARS}, as in the bar)",
    )
    arguments = parser.parse_args()

    if arguments.list:
        return list_devices()
    if arguments.bars < 2 or arguments.bars % 2:
        parser.error("--bars must be an even number of at least 2")
    return preview(arguments.device, arguments.bars)


if __name__ == "__main__":
    sys.exit(main())
