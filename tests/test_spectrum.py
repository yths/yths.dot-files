"""``shared.spectrum``: the block ladder, and the maths behind the level meter."""

import numpy
import pytest
from shared import spectrum


def stereo(rows: int, amplitude: float = 1.0, seed: int = 0) -> numpy.ndarray:
    return numpy.random.default_rng(seed).normal(0, amplitude, size=(rows, 2))


# The ladder is offset from U+2580 so that height 1 lands on the one-eighth block. Offsetting
# from U+2581 -- which looks like the obvious choice -- skips it and lands a full bar on
# U+2589, a *horizontal* seven-eighths block that fills the wrong way.
def test_the_ladder_covers_every_block_from_one_eighth_to_full() -> None:
    heights = numpy.arange(1, spectrum.BLOCK_STEPS + 1) / spectrum.BLOCK_STEPS
    assert spectrum.render(heights) == "▁▂▃▄▅▆▇█"


def test_silence_is_a_space_not_a_block() -> None:
    assert spectrum.render(numpy.zeros(4)) == "    "


def test_a_full_bar_is_the_vertical_full_block() -> None:
    assert spectrum.render(numpy.ones(1)) == "█"
    assert ord("█") == spectrum.BLOCK_BASE + spectrum.BLOCK_STEPS


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


def test_a_real_signal_reaches_the_upper_blocks() -> None:
    loud = spectrum.render(spectrum.levels(stereo(2048, amplitude=3.0), 16))
    assert loud.strip() != ""
    assert any(character in loud for character in "▆▇█")


# The left channel is mirrored so its low frequencies sit at the centre; the meter opens
# outwards rather than reading left to right twice.
def test_the_meter_is_symmetric_for_identical_channels() -> None:
    mono = numpy.random.default_rng(1).normal(0, 1, size=(2048, 1))
    values = spectrum.levels(numpy.hstack([mono, mono]), 16)
    assert numpy.allclose(values[:8][::-1], values[8:])
