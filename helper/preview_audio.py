"""Preview the qtile audio meter in a terminal and pick an output device.

The bar's level meter is eight characters of block glyphs in a status bar, which makes it a
poor place to work out why it is flat: is the device wrong, is nothing playing, or is the
rendering broken? This draws the same meter full-width in a terminal, from
``configuration/qtile/shared/spectrum.py`` -- the module the widget itself renders through --
so what appears here is what the bar will draw.

Usage::

    python helper/preview_audio.py --list          # outputs, with their sink indices
    python helper/preview_audio.py                 # preview the system default output
    python helper/preview_audio.py --device 31     # preview a specific sink
    python helper/preview_audio.py --device analog # ... or the first whose name matches

Pass the chosen index to ``WidgetAudio(device_id=...)`` in ``configuration/qtile/config.py``.
"""

import argparse
import os
import subprocess
import sys

import numpy

#: This file's repository, resolved through any symlink used to invoke it.
_REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# The qtile configuration directory is on sys.path when qtile loads the widgets; it is not
# when this runs as a script. Adding it is what lets the preview share the widget's own
# rendering rather than carrying a copy that drifts out of step -- which is exactly what
# the harness this replaced had done.
sys.path.insert(0, os.path.join(_REPOSITORY_ROOT, "configuration", "qtile"))

import shared.audio_capture  # noqa: E402
import shared.spectrum  # noqa: E402

#: Matches the widget's default, so the preview shows the same number of bars as the bar.
DEFAULT_NUM_BARS = 16


def list_devices() -> int:
    """Print output sinks with the indices the widget expects."""
    try:
        outputs = shared.audio_capture.output_monitors()
        default = shared.audio_capture.default_output()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"audio outputs are unavailable: {error}", file=sys.stderr)
        return 1
    for output in outputs:
        if not output.get("monitor_source"):
            continue
        marker = "*" if output["name"] == default else " "
        print(f"{marker} {output['index']:>3}  {output['name']}")
    print("\n* is the system default output.")
    return 0


def preview(device: str | int | None, num_bars: int) -> int:
    """Draw the meter until interrupted. Returns a process exit status."""
    try:
        outputs = shared.audio_capture.output_monitors()
        default = shared.audio_capture.default_output()
        if isinstance(device, str):
            output = next((item for item in outputs if device in item["name"] and item.get("monitor_source")), None)
        elif isinstance(device, int):
            output = next((item for item in outputs if item["index"] == device and item.get("monitor_source")), None)
        else:
            output = shared.audio_capture.select_output(outputs, default, None, 0)
        if output is None:
            print(f"output {device!r} is unavailable", file=sys.stderr)
            return 1
        monitor = shared.audio_capture.OutputMonitor(output["monitor_source"])
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"cannot open device {device!r}: {error}", file=sys.stderr)
        return 1

    print(f"Capturing output {output['name']} — Ctrl-C to stop.")
    levels = numpy.zeros(num_bars)
    try:
        while True:
            levels = 0.8 * levels + 0.2 * shared.spectrum.levels(monitor.read(), num_bars)
            meter = shared.spectrum.render(levels)
            print(f"\r|{meter}|", end="", flush=True)
    except KeyboardInterrupt:
        print()
        return 0
    except (OSError, ValueError) as error:
        print(f"\ncapture failed: {error}", file=sys.stderr)
        return 1
    finally:
        monitor.close()


def parse_device(value: str) -> str | int:
    """A device is an index if it looks like one, otherwise a name to match on."""
    return int(value) if value.lstrip("-").isdigit() else value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--list",
        action="store_true",
        help="list output devices and their sink indices, then exit",
    )
    parser.add_argument(
        "--device",
        type=parse_device,
        default=None,
        help="sink index or name substring (default: the system default output)",
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
