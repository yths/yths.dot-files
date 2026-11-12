"""Recolouring a stock VSCode theme: the walk, the naming, and the two mapping methods.

The perceptual matching itself now lives in `helper/color_match.py` and is tested in
`tests/test_color_match.py` -- including the selection-invisibility rule, which is the defect
recorded in docs/issues.md under the VSCode selection-visibility entry. What is left here is
what `patch_vsc` still owns: finding every colour in a theme file whatever it is nested
inside, and the difference between mapping each mode against its own palette and writing one
mode's colours for another's matches.
"""

import color_match
import patch_vsc
import pytest

#: Deliberately far apart in CAM16-UCS, so a wrong match is unambiguous.
PALETTE = {
    "dark": {"background": "#000000", "foreground": "#ffffff", "red": "#ff0000",
             "blue": "#0000ff", "highlight": "#00ff00"},
    "light": {"background": "#ffffff", "foreground": "#000000", "red": "#cc0000",
              "blue": "#0000cc", "highlight": "#00cc00"},
}


@pytest.fixture(scope="module")
def palette_map() -> dict:
    return patch_vsc.build_palette_map(PALETTE)


# ------------------------------------------------------------------------- the walk


def test_replacement_reaches_into_nested_lists_and_dicts(palette_map: dict) -> None:
    """A theme's colours are three containers deep; a walk that stopped short would
    silently leave the syntax highlighting stock."""
    replaced = patch_vsc.dict_replace_value(
        {"tokenColors": [{"settings": {"foreground": "#fe0101"}}]}, palette_map["dark"]
    )
    assert replaced["tokenColors"][0]["settings"]["foreground"] == "#ff0000"


def test_non_colour_values_pass_through_untouched(palette_map: dict) -> None:
    """`scope` strings, names and flags sit beside the colours in the same dicts."""
    original = {
        "name": "dot files", "semanticHighlighting": True, "version": 3,
        "scope": "#notahex", "fontStyle": "italic",
        "scopes": ["punctuation.definition", "storage.modifier"],
    }
    assert patch_vsc.dict_replace_value(dict(original), palette_map["dark"]) == original


def test_a_highlight_background_is_still_excluded_through_the_walk(palette_map: dict) -> None:
    """The exclusion is keyed on the field name, so it has to survive the recursion."""
    replaced = patch_vsc.dict_replace_value(
        {"editor.selectionBackground": "#010101"}, palette_map["dark"]
    )
    assert replaced["editor.selectionBackground"] != "#000000"
    assert patch_vsc.dict_replace_value(
        {"editor.background": "#010101"}, palette_map["dark"]
    )["editor.background"] == "#000000"


# ------------------------------------------------------------------- building a theme


def test_build_themes_names_both_modes(palette_map: dict) -> None:
    defaults = {mode: {"name": "Untitled", "colors": {}} for mode in patch_vsc.MODES}
    themes = patch_vsc.build_themes(defaults, palette_map, "nearest_neighbor")
    assert themes["dark"]["name"] == "dot files (dark)"
    assert themes["light"]["name"] == "dot files (light)"


def test_nearest_neighbour_maps_each_mode_against_its_own_palette(palette_map: dict) -> None:
    defaults = {mode: {"colors": {"editor.foreground": "#fe0101"}} for mode in patch_vsc.MODES}
    themes = patch_vsc.build_themes(defaults, palette_map, "nearest_neighbor")
    assert themes["dark"]["colors"]["editor.foreground"] == "#ff0000"
    assert themes["light"]["colors"]["editor.foreground"] == "#cc0000"


def test_reference_writes_the_dark_value_for_whatever_the_light_palette_matched(
    palette_map: dict,
) -> None:
    """The light theme still matches against the light palette."""
    defaults = {mode: {"colors": {"editor.foreground": "#fe0101"}} for mode in patch_vsc.MODES}
    themes = patch_vsc.build_themes(defaults, palette_map, "reference")
    assert themes["light"]["colors"]["editor.foreground"] == "#ff0000"


# --------------------------------------------------------------------- the stock themes


def test_the_themes_this_patcher_recolours_are_in_the_repository() -> None:
    """build_themes is only meaningful against the stock themes; a rename would strand it."""
    themes = patch_vsc.load_default_themes("configuration/vscode")
    assert set(themes) == set(patch_vsc.MODES)
    assert themes["dark"]["colors"], "the stock dark theme carries no colours"
    assert themes["light"]["colors"], "the stock light theme carries no colours"


def test_every_colour_in_the_stock_themes_is_one_the_matcher_can_read() -> None:
    """A value the matcher returns None for is one that silently stays stock."""
    themes = patch_vsc.load_default_themes("configuration/vscode")
    for mode, theme in themes.items():
        for key, value in theme["colors"].items():
            assert color_match.to_rgb(value) is not None, f"{mode}: {key} = {value!r}"
