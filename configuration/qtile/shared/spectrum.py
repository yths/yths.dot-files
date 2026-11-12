"""Shared FFT-to-block-glyph rendering for the audio level meter.

The bar's level meter and the ``helper/preview_audio.py`` harness draw the same picture from
the same samples, so the maths lives here rather than in either of them.

Everything here is pure: it takes samples and returns numbers or a string, with no reference
to PortAudio, qtile or the bar. That is what lets the harness preview exactly what the bar
draws, rather than something that resembles it.
"""

from collections.abc import Sequence

import numpy
import symbols as vocabulary

#: ``chr(BLOCK_BASE + height)`` for ``height`` in 1..8 walks U+2581 LOWER ONE EIGHTH BLOCK
#: through U+2588 FULL BLOCK. Kept because ``tests/test_spectrum.py`` pins the block ladder
#: to those codepoints, and because it is what the shipped bundle overrides ``meter.ramp``
#: with -- but ``render`` no longer computes from it: a ladder a theme cannot replace is
#: exactly what the symbol vocabulary exists to undo.
BLOCK_BASE = 0x2580

#: Number of distinct bar heights above silence.
BLOCK_STEPS = 8

#: Used when no ramp is passed in. Taken from the vocabulary rather than restated, so there
#: is one ASCII ladder rather than two that can drift apart.
DEFAULT_RAMP = vocabulary.SYMBOLS["meter.ramp"]

#: Drawn for a bar with no signal. A space, not ``▁``, so silence reads as empty -- and in
#: the vocabulary rather than here, so a theme that wants a visible floor can set one.
SILENCE = vocabulary.SYMBOLS["meter.silence"]

#: Only the lowest eighth of the FFT is summed into the bars. Above that is mostly
#: inaudible content that flattens the visible range of everything below it.
SPECTRUM_FRACTION = 8

#: Floor for the normalisation divisor. Without it, near-silence is divided by its own tiny
#: peak and the meter shows full bars of noise.
NOISE_FLOOR = 2


def compress(values: numpy.ndarray, bins: int) -> numpy.ndarray:
    """Sum ``values`` into ``bins`` contiguous buckets of near-equal width.

    Raises ``ValueError`` if there are fewer values than requested buckets, which is how a
    short or empty capture buffer is signalled to the caller.
    """
    if bins > len(values):
        raise ValueError("cannot compress into more bins than there are values")
    edges = numpy.linspace(0, len(values), bins + 1, dtype=int)
    return numpy.array([values[edges[i] : edges[i + 1]].sum() for i in range(bins)])


def levels(samples: numpy.ndarray, num_bars: int) -> numpy.ndarray:
    """Normalised 0..1 level per bar for one block of stereo ``samples``.

    The left channel occupies the first half of the returned array, mirrored so its low
    frequencies sit at the centre; the right channel occupies the second half in natural
    order. The result is a meter that opens outwards from the middle.

    Raises ``ValueError`` for a capture too short to fill the bars.
    """
    magnitudes = numpy.abs(numpy.fft.fft(samples - numpy.mean(samples, axis=0), axis=0))
    audible = magnitudes[: len(magnitudes) // SPECTRUM_FRACTION, :]
    left = compress(audible[:, 0], num_bars // 2)
    right = compress(audible[:, 1], num_bars // 2)
    combined = numpy.concatenate((left[::-1], right))
    return combined / numpy.max([numpy.max(combined), NOISE_FLOOR])


def render(bar_levels: numpy.ndarray, ramp: Sequence[str] | None = None) -> str:
    """One character per bar, taken from ``ramp`` by height.

    ``ramp`` is the active vocabulary's ``meter.ramp``, passed down from config.py the way
    the colours are. Without one it falls back to ASCII rather than to the block elements:
    the whole point of the vocabulary is that a machine with no suitable font still draws a
    meter, and a computed ``chr(BLOCK_BASE + h)`` cannot be overridden by a theme.
    """
    rungs = tuple(ramp) if ramp else DEFAULT_RAMP
    heights = numpy.round(bar_levels * len(rungs)).astype(int)
    return "".join(rungs[h - 1] if h > 0 else SILENCE for h in heights)
