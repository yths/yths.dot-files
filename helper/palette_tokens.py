"""The palette's vocabulary: the tokens a theme sets, in the order ``palette.json`` holds them.

A palette is ``{"light": {token: hex}, "dark": {token: hex}}`` with exactly these tokens in
both modes. chromalytica writes that file and holds the same tuple in its
``vocabulary.TOKENS``, with a test that reads this repository's tracked bundle and fails if
the two disagree; ``tests/test_palette_tokens.py`` holds the bundle to the tuple from this
side. What each token means is in docs/palette-semantics.md.

The three greys at the end are the newest. A bundle exported before them carries twenty-one
tokens, and :func:`complete` gives it the missing three from the greys it does have, so an
older theme keeps working until it is exported again.

No third-party import: qtile's ``config.py`` and every patcher load this, and
``patch_configurations`` keeps ``colour`` off the path of the patchers that do not need it.
"""

#: Every token, in file order. The order is part of the format: an exported palette is
#: diffed against the one it replaces, and a reordered file is a diff of every line.
TOKENS: tuple[str, ...] = (
    "background",
    "foreground",
    "highlight",
    "success",
    "failure",
    "notification",
    "red",
    "green",
    "blue",
    "cyan",
    "magenta",
    "yellow",
    "warning",
    "red_variant",
    "green_variant",
    "blue_variant",
    "cyan_variant",
    "magenta_variant",
    "yellow_variant",
    "neutral",
    "foreground_variant",
    "surface",
    "surface_variant",
    "foreground_muted",
)

#: The greys, from the background outward. Nothing chromatic: these are what a surface or a
#: run of text may be without saying anything.
GREYS: tuple[str, ...] = (
    "background",
    "surface",
    "surface_variant",
    "neutral",
    "foreground_muted",
    "foreground",
    "foreground_variant",
)

#: The greys text may be drawn in. ``surface`` and ``surface_variant`` are absent because
#: they are a step off the background by design, which is what makes them unreadable on it.
TEXT_GREYS: frozenset[str] = frozenset(
    {"background", "neutral", "foreground_muted", "foreground", "foreground_variant"}
)

#: The greys a raised surface may be drawn in: a cell, a hovered row, an inactive selection.
SURFACE_GREYS: frozenset[str] = frozenset({"surface", "surface_variant"})

#: How :func:`complete` makes each token a bundle may predate: (from, toward, weight). A
#: quarter of the way from ``background`` to ``neutral`` shows a cell's edges against the bar
#: and keeps ``foreground`` text above 4.5:1 on it; twice that is the next step out; and
#: muted text sits halfway between the border grey and the text grey.
DERIVED: dict[str, tuple[str, str, float]] = {
    "surface": ("background", "neutral", 0.25),
    "surface_variant": ("background", "neutral", 0.5),
    "foreground_muted": ("neutral", "foreground", 0.5),
}


def mix(first: str, second: str, weight: float) -> str:
    """``first`` moved ``weight`` of the way to ``second``, channel by channel, as a hex."""
    start, end = (
        [int(value.lstrip("#")[index : index + 2], 16) for index in (0, 2, 4)]
        for value in (first, second)
    )
    return "#" + "".join(
        f"{round(a + (b - a) * weight):02x}" for a, b in zip(start, end, strict=True)
    )


def derived(palette: dict[str, dict[str, str]]) -> list[str]:
    """The tokens :func:`complete` would have to make for ``palette``, in file order."""
    return [
        token for token in DERIVED
        if any(token not in colours for colours in palette.values())
    ]


def complete(palette: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """``palette`` with every token in ``DERIVED`` present, in both modes.

    A token the palette already carries is kept as it is: the generator chose it against the
    whole grid, and a mix of two neighbours is only a stand-in for that. A mode missing the
    greys a derivation starts from is left without the token, so the consumer that reads it
    fails on the name it asked for rather than on one invented here.
    """
    completed = {}
    for mode, colours in palette.items():
        filled = dict(colours)
        for token, (start, end, weight) in DERIVED.items():
            if token not in filled and start in filled and end in filled:
                filled[token] = mix(filled[start], filled[end], weight)
        completed[mode] = filled
    return completed
