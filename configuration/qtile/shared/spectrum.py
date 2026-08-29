"""Shared FFT-to-block-glyph rendering for the audio level meter.

The bar's level meter and the ``helper/preview_audio.py`` harness draw the same picture from
the same samples, so the maths lives here rather than in both. It was in both, and they had
already drifted: the harness still offset from U+2581, which skips ``▁`` and lands a full
bar on ``▉`` (a *horizontal* seven-eighths block), and it summed the lower half of the
spectrum where the widget sums the lower eighth.

Everything here is pure: it takes samples and returns numbers or a string, with no reference
to PortAudio, qtile or the bar. That is what lets the harness preview exactly what the bar
will draw.
"""

import numpy

#: ``chr(BLOCK_BASE + height)`` for ``height`` in 1..8 walks U+2581 LOWER ONE EIGHTH BLOCK
#: through U+2588 FULL BLOCK. Height 0 is a space, so the ladder is offset from U+2580 to
#: put height 1 on ``▁`` rather than skipping it.
BLOCK_BASE = 0x2580

#: Number of distinct bar heights above silence.
BLOCK_STEPS = 8

#: Drawn for a bar with no signal. A space, not ``▁``, so silence reads as empty.
SILENCE = " "

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


def render(bar_levels: numpy.ndarray) -> str:
    """Block glyphs for normalised levels, one character per bar."""
    heights = numpy.round(bar_levels * BLOCK_STEPS).astype(int)
    return "".join(chr(BLOCK_BASE + h) if h > 0 else SILENCE for h in heights)
