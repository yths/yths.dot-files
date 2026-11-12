"""The perceptual matcher the VSCode and qutebrowser patchers both resolve colours with.

It exists because the algorithm was written twice and the copies had already drifted: one
stripped alpha with `len(v) == 9`, the other with `value[:7]`, and the second reimplemented
the search because it needed the label and the distance the first computed and discarded.
`nearest` returns all three, so the colour a patcher writes and the number the report prints
come from one comparison rather than two that agree by luck.
"""

import color_match
import pytest

#: Deliberately far apart in CAM16-UCS, so a wrong match is unambiguous rather than marginal.
PALETTE = {
    "dark": {"background": "#000000", "foreground": "#ffffff", "red": "#ff0000",
             "blue": "#0000ff", "highlight": "#00ff00"},
    "light": {"background": "#ffffff", "foreground": "#000000", "red": "#cc0000",
              "blue": "#0000cc", "highlight": "#00cc00"},
}


@pytest.fixture(scope="module")
def palette_map() -> dict:
    return color_match.build_palette_map(PALETTE)


# ------------------------------------------------------------------------ reading a colour


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("#ff0000", (1.0, 0.0, 0.0)),
        ("#ff000080", (1.0, 0.0, 0.0)),      # alpha is not a perceptual dimension
        ("#FF0000", (1.0, 0.0, 0.0)),
        ("red", (1.0, 0.0, 0.0)),
        ("White", (1.0, 1.0, 1.0)),          # names are matched case-insensitively
    ],
)
def test_a_colour_is_read_however_it_is_written(value: str, expected: tuple) -> None:
    assert color_match.to_rgb(value) == pytest.approx(expected)


# Everything qutebrowser's stock configuration holds that is *not* a colour. Handing these to
# the matcher has to be safe, because the patcher hands it every default it finds.
@pytest.mark.parametrize(
    "value",
    [
        "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #888888, stop:1 #505050)",
        "rgba(0, 0, 0, 80%)",
        "1px solid gray",
        "rgb", "smart", "auto", "lightness-cielab",
        None, False, True, 0, 256, 0.0, "", "#fff", "#notahex",
    ],
)
def test_anything_that_is_not_a_colour_reads_as_none(value: object) -> None:
    assert color_match.to_rgb(value) is None


def test_every_css_name_qt_understands_is_known() -> None:
    """Qt's named colours are the SVG set, which is what CSS_COLOR_3 carries."""
    assert len(color_match.NAMED) > 140
    for name in ("white", "black", "grey", "darkgrey", "darkslategray", "lime", "aqua",
                 "darkorange", "darkseagreen", "seagreen", "purple", "orange"):
        assert color_match.to_rgb(name) is not None, name


# ------------------------------------------------------------------------ matching


def test_a_colour_matches_the_nearest_token(palette_map: dict) -> None:
    assert color_match.nearest("#fe0101", palette_map["dark"]).label == "red"
    assert color_match.nearest("#010199", palette_map["dark"]).label == "blue"


def test_a_named_colour_matches_too(palette_map: dict) -> None:
    """The reason qutebrowser can be themed at all: 62 of its defaults are names."""
    assert color_match.nearest("red", palette_map["dark"]).label == "red"
    assert color_match.nearest("black", palette_map["dark"]).label == "background"


def test_the_distance_is_zero_for_an_exact_hit(palette_map: dict) -> None:
    assert color_match.nearest("#ff0000", palette_map["dark"]).delta == pytest.approx(0, abs=1e-6)


def test_a_far_colour_reports_a_large_distance(palette_map: dict) -> None:
    """The number the report is built on: a big ΔE is a visibly different colour."""
    near = color_match.nearest("#fe0101", palette_map["dark"]).delta
    far = color_match.nearest("#808080", palette_map["dark"]).delta
    assert far > near


def test_a_non_colour_matches_nothing(palette_map: dict) -> None:
    assert color_match.nearest("qlineargradient(x1:0)", palette_map["dark"]) is None
    assert color_match.nearest("#ff0000", []) is None


# VSCode writes eight-digit hex for translucent surfaces; dropping the alpha would turn a wash
# over the editor into a solid block.
def test_replacing_keeps_the_alpha(palette_map: dict) -> None:
    assert color_match.replace("#fe010180", palette_map["dark"]) == "#ff000080"
    assert color_match.replace("#fe0101", palette_map["dark"]) == "#ff0000"


def test_replacing_leaves_a_non_colour_alone(palette_map: dict) -> None:
    for value in ("#notahex", "rgb", "qlineargradient(x1:0)"):
        assert color_match.replace(value, palette_map["dark"]) == value


# The indirection behind patch_vsc's `reference` method: choose in one palette, write from
# another, keyed by label.
def test_a_lookup_writes_the_other_palettes_colour(palette_map: dict) -> None:
    found = color_match.nearest("#fe0101", palette_map["light"], palette_map["dark"])
    assert found.label == "red"
    assert found.hex == "#ff0000", "matched in light, written from dark"


# ------------------------------------------------------- the selection-invisibility rule


def test_a_highlight_background_never_matches_the_editor_background(palette_map: dict) -> None:
    """Painting a selection in the colour it is selecting against makes it invisible."""
    candidates = color_match.filter_candidates("editor.selectionBackground", palette_map["dark"])
    assert color_match.nearest("#010101", candidates).label != "background"


def test_an_ordinary_background_still_matches_the_background(palette_map: dict) -> None:
    """The exclusion is scoped to highlight-ish keys; widening it would flatten the theme."""
    candidates = color_match.filter_candidates("editor.background", palette_map["dark"])
    assert color_match.nearest("#010101", candidates).label == "background"


@pytest.mark.parametrize(
    "key",
    ["editor.selectionBackground", "list.hoverBackground", "list.dropBackground",
     "editor.findMatchBackground", "editor.rangeHighlightBackground",
     "editor.focusedStackFrameHighlightBackground"],
)
def test_every_highlight_marker_excludes_the_background(key: str) -> None:
    assert color_match.excludes_background(key)


@pytest.mark.parametrize(
    "key", ["editor.background", "sideBar.background", None, "", "editor.foreground"]
)
def test_nothing_else_excludes_it(key: str | None) -> None:
    assert not color_match.excludes_background(key)


# `darkgreen` is nine characters, and so are `lightpink`, `slateblue` and `royalblue`. The
# alpha slice was taken on length alone, so replacing one appended `en` to the palette colour
# and produced `#569c67en` -- which qutebrowser rejects and Qt draws as nothing.
@pytest.mark.parametrize(
    "name", ["darkgreen", "lightpink", "slateblue", "royalblue", "peachpuff"]
)
def test_a_nine_letter_colour_name_is_not_mistaken_for_alpha(
    palette_map: dict, name: str
) -> None:
    assert len(name) == 9, "this test is only meaningful for a nine-character name"
    replaced = color_match.replace(name, palette_map["dark"])
    assert len(replaced) == 7, f"{name} became {replaced!r}"
    assert replaced in {entry["hex"] for entry in palette_map["dark"]}
