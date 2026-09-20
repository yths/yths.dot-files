"""``shared.spectrum``: the block ladder, and the maths behind the level meter."""

import json
import pathlib

import numpy
import pytest
import symbols
from shared import spectrum

#: What the shipped bundle overrides ``meter.ramp`` with -- the block elements the meter was
#: built around, now supplied by the theme rather than computed.
BUNDLE_RAMP = tuple(
    json.loads(
        (pathlib.Path(__file__).resolve().parent.parent / "assets/default/config.json")
        .read_text()
    )["symbols"]["meter.ramp"]
)


def stereo(rows: int, amplitude: float = 1.0, seed: int = 0) -> numpy.ndarray:
    return numpy.random.default_rng(seed).normal(0, amplitude, size=(rows, 2))


# The ladder used to be computed as `chr(BLOCK_BASE + height)`, offset from U+2580 so that
# height 1 landed on the one-eighth block: offsetting from U+2581 -- which looks like the
# obvious choice -- skips it and lands a full bar on U+2589, a *horizontal* seven-eighths
# block that fills the wrong way. The ladder is now the theme's, so the property is asserted
# of what the shipped bundle installs rather than of the arithmetic that replaced it.
def test_the_shipped_ladder_covers_every_block_from_one_eighth_to_full() -> None:
    ramp = BUNDLE_RAMP
    heights = numpy.arange(1, len(ramp) + 1) / len(ramp)
    assert spectrum.render(heights, ramp) == "▁▂▃▄▅▆▇█"
    assert ord(ramp[-1]) == spectrum.BLOCK_BASE + spectrum.BLOCK_STEPS


def test_silence_is_a_space_not_a_block() -> None:
    assert spectrum.render(numpy.zeros(4)) == "    "
    assert spectrum.render(numpy.zeros(4), BUNDLE_RAMP) == "    "


def test_a_full_bar_is_the_last_rung_of_whatever_ramp_it_was_given() -> None:
    assert spectrum.render(numpy.ones(1), BUNDLE_RAMP) == "█"
    assert spectrum.render(numpy.ones(1), tuple("abcdefgh")) == "h"


# The meter is one of the surfaces that breaks worst without a Nerd Font, so the ramp it
# falls back to when a theme supplies none must not itself need one.
def test_the_default_ramp_is_ascii_and_is_the_vocabularys() -> None:
    assert all(rung.isascii() for rung in spectrum.DEFAULT_RAMP)
    assert symbols.SYMBOLS["meter.ramp"] == spectrum.DEFAULT_RAMP
    assert spectrum.render(numpy.ones(1)).isascii()


def test_render_returns_one_character_per_bar() -> None:
    assert len(spectrum.render(numpy.linspace(0, 1, 16))) == 16


def test_compress_sums_into_the_requested_buckets() -> None:
    assert list(spectrum.compress(numpy.ones(8), 4)) == [2, 2, 2, 2]
    assert spectrum.compress(numpy.arange(10), 5).sum() == numpy.arange(10).sum()


# A short capture buffer is signalled by ValueError, which the caller uses to keep the
# previous frame on screen rather than blanking the meter.
def test_compress_refuses_more_buckets_than_values() -> None:
    with pytest.raises(ValueError, match="more bins than there are values"):
        spectrum.compress(numpy.ones(3), 4)


def test_levels_raises_on_a_capture_too_short_to_fill_the_bars() -> None:
    with pytest.raises(ValueError):
        spectrum.levels(stereo(4), 16)


def test_levels_returns_one_value_per_bar_between_zero_and_one() -> None:
    values = spectrum.levels(stereo(2048), 16)
    assert len(values) == 16
    assert values.min() >= 0.0
    assert values.max() <= 1.0


# Without the floor, near-silence is divided by its own tiny peak and the meter shows full
# bars of noise.
def test_near_silence_stays_near_the_bottom() -> None:
    quiet = spectrum.levels(stereo(2048, amplitude=1e-6), 16)
    assert quiet.max() < 0.1
    assert spectrum.render(quiet).strip() == ""


@pytest.mark.parametrize("ramp", [None, BUNDLE_RAMP], ids=["ascii", "bundle"])
def test_a_real_signal_reaches_the_upper_rungs(ramp: tuple[str, ...] | None) -> None:
    """Whatever ladder is in use, a loud signal has to reach the top of it."""
    rungs = ramp or spectrum.DEFAULT_RAMP
    loud = spectrum.render(spectrum.levels(stereo(2048, amplitude=3.0), 16), ramp)
    assert loud.strip() != ""
    assert any(rung in loud for rung in rungs[-3:])


# The left channel is mirrored so its low frequencies sit at the centre; the meter opens
# outwards rather than reading left to right twice.
def test_the_meter_is_symmetric_for_identical_channels() -> None:
    mono = numpy.random.default_rng(1).normal(0, 1, size=(2048, 1))
    values = spectrum.levels(numpy.hstack([mono, mono]), 16)
    assert numpy.allclose(values[:8][::-1], values[8:])
