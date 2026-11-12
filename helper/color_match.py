"""Match an arbitrary colour to the nearest palette token, perceptually.

Two patchers resolve colours rather than being told which token to use: VSCode recolours a
stock theme, and qutebrowser recolours its stock defaults. Both ask the same question -- of
the twenty-one colours this theme has, which is this one closest to? -- and "closest" means
CAM16-UCS ΔE rather than anything in RGB, because RGB distance says a dark blue and a dark
green are neighbours and the eye does not.

The algorithm lived in ``patch_vsc`` with a second copy in ``list_palette``, and the two had
already drifted: one stripped alpha with ``len(v) == 9``, the other with ``value[:7]``, and
the second reimplemented the search because it needed the label and the distance that the
first computed and threw away. :func:`nearest` returns all three, so a caller that wants a
colour and a caller that wants a number ask the same function.

Named colours resolve through ``colour.notation.CSS_COLOR_3`` -- 147 entries, which covers
every name qutebrowser's stock configuration uses -- rather than a table written out here
that would have to be kept true.
"""

from typing import Any, NamedTuple

import colour

#: CSS/Qt colour names, lowercased. Qt's named colours are the SVG set, which is this one.
NAMED: dict[str, str] = {
    name.lower(): value for name, value in colour.notation.CSS_COLOR_3.items()
}

#: Keys whose *background* is a highlight drawn over the editor rather than the editor's own
#: surface. Matching one of these to the background token paints a selection in the colour it
#: is selecting against, which is invisible -- the defect recorded in docs/issues.md under the
#: VSCode selection-visibility entry.
HIGHLIGHT_KEY_MARKERS = (
    "selection",
    "highlight",
    "hover",
    "focus",
    "drop",
    "match",
    "range",
)

#: The token dropped from the candidates for those keys.
HIGHLIGHT_EXCLUDED_LABELS = frozenset({"background"})


class Match(NamedTuple):
    """The palette token nearest a colour, and how far away it was.

    ``delta`` is the reason this is a NamedTuple rather than a bare string: a patcher uses
    ``hex``, and the report in ``helper/list_color_distance.py`` uses ``delta``, and they must
    be describing the same comparison or the report is about a replacement that did not happen.
    """

    label: str
    hex: str
    delta: float


def to_rgb(value: str) -> tuple[float, float, float] | None:
    """A colour as an 0..1 RGB triple, or ``None`` if this is not one.

    Accepts ``#rrggbb``, ``#rrggbbaa`` (alpha ignored -- it is not a perceptual dimension and
    CAM16-UCS has nowhere to put it) and any CSS colour name. Everything else is something the
    caller must leave alone: a gradient, an enum, a number, ``None``.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text.startswith("#"):
        text = NAMED.get(text.lower(), "")
        if not text:
            return None
    if len(text) not in (7, 9):
        return None
    try:
        return tuple(int(text[index : index + 2], 16) / 255 for index in (1, 3, 5))
    except ValueError:
        return None


def _cam16(rgb: tuple[float, float, float]) -> Any:
    return colour.XYZ_to_CAM16UCS(colour.sRGB_to_XYZ(rgb))


def build_palette_map(palette: dict[str, dict[str, str]]) -> dict[str, list[dict[str, Any]]]:
    """Precompute each palette colour's CAM16-UCS coordinates, per mode.

    Done once up front because the search compares every candidate against every colour it is
    asked about, and the conversion is the expensive half of that.
    """
    return {
        mode: [
            {"label": label, "hex": hex_value, "cam16": _cam16(to_rgb(hex_value))}
            for label, hex_value in colours.items()
        ]
        for mode, colours in palette.items()
    }


def excludes_background(key: str | None) -> bool:
    """Whether this key names a highlight surface rather than a background."""
    if not key:
        return False
    lowered = key.lower()
    if "background" not in lowered:
        return False
    return any(marker in lowered for marker in HIGHLIGHT_KEY_MARKERS)


def filter_candidates(key: str | None, candidates: list) -> list:
    """The palette a key may be matched against."""
    if excludes_background(key):
        return [c for c in candidates if c["label"] not in HIGHLIGHT_EXCLUDED_LABELS]
    return candidates


def nearest(value: str, candidates: list, lookup: list | None = None) -> Match | None:
    """The closest candidate to ``value``, or ``None`` if ``value`` is not a colour.

    ``lookup`` is the indirection behind ``patch_vsc``'s ``reference`` method: the winner is
    chosen in ``candidates`` and then read back out of ``lookup`` *by label*, so a light theme
    can be matched against the light palette and written in the dark one's colours.
    """
    rgb = to_rgb(value)
    if rgb is None or not candidates:
        return None
    target = _cam16(rgb)
    best = min(
        candidates,
        key=lambda candidate: float(
            colour.delta_E(target, candidate["cam16"], method="CAM16-UCS")
        ),
    )
    delta = float(colour.delta_E(target, best["cam16"], method="CAM16-UCS"))
    if lookup is not None:
        for entry in lookup:
            if entry["label"] == best["label"]:
                return Match(best["label"], entry["hex"], delta)
    return Match(best["label"], best["hex"], delta)


def replace(value: str, candidates: list, lookup: list | None = None) -> str:
    """``value`` recoloured to the nearest candidate, keeping any alpha it carried.

    VSCode writes eight-digit hex for translucent surfaces; dropping the alpha would turn a
    wash over the editor into a solid block. A value that is not a colour comes back unchanged,
    which is what lets a caller hand this every string it finds.
    """
    # Hex only. A named colour can be nine characters long too -- `darkgreen`, `lightpink` --
    # and slicing an "alpha" off one of those appends `en` to the colour that replaces it.
    hexed = isinstance(value, str) and value.startswith("#")
    alpha = value[7:9] if hexed and len(value) == 9 else ""
    found = nearest(value, candidates, lookup)
    return value if found is None else found.hex + alpha


#: WCAG 2's minimum contrast ratio for body text.
MIN_TEXT_CONTRAST = 4.5

#: The palette tokens text may be re-picked from: the greys, per docs/palette-semantics.md.
#: A chromatic token reads, but a side bar of teal file names is not what a grey label meant.
TEXT_LABELS = frozenset({"foreground", "foreground_variant", "neutral", "background"})


def _luminance(rgb: tuple[float, float, float]) -> float:
    """WCAG relative luminance of an sRGB colour with channels in 0..1."""
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(first: str, second: str) -> float | None:
    """The WCAG contrast ratio between two colours, or ``None`` if either is not one."""
    rgbs = [to_rgb(value) for value in (first, second)]
    if None in rgbs:
        return None
    lighter, darker = sorted((_luminance(rgb) for rgb in rgbs), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def legible(value: str, background: str, candidates: list) -> str | None:
    """The candidate nearest ``value`` that reads as text on ``background``.

    Matching every colour on its own can land a text colour and the surface under it on one
    token -- a palette with few greys has nowhere else to put a mid-grey label and a tinted
    selection. This is the second look at the pair: among the candidates that reach
    ``MIN_TEXT_CONTRAST`` against the background, the one nearest the colour the text was
    meant to be; failing that, whichever contrasts most. ``None`` if ``value`` is not a colour.
    """
    candidates = [candidate for candidate in candidates if candidate["label"] in TEXT_LABELS]
    if to_rgb(value) is None or to_rgb(background) is None or not candidates:
        return None
    readable = [
        candidate for candidate in candidates
        if (contrast(candidate["hex"], background) or 0) >= MIN_TEXT_CONTRAST
    ]
    if readable:
        found = nearest(value, readable)
        return found.hex if found else None
    return max(candidates, key=lambda candidate: contrast(candidate["hex"], background) or 0)["hex"]
