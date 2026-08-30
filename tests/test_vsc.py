"""The VSCode patcher: perceptual colour matching, and the one exclusion that is not perceptual.

`patch_vsc` recolours the two stock themes by replacing every hex it finds with the nearest
palette colour in CAM16-UCS. That is right almost everywhere and wrong for one family of keys:
a selection or hover *background* matched onto the editor background is perceptually nearest
and visually useless, because the highlight then cannot be seen. `_excludes_background` drops
`background` from the candidates for exactly those keys -- the fix recorded in docs/issues.md
under the VSCode selection-visibility entry.
"""

import patch_vsc
import pytest

#: Deliberately far apart in CAM16-UCS, so a nearest-match assertion is unambiguous.
PALETTE = {
    "dark": {"background": "#000000", "foreground": "#ffffff", "red": "#ff0000",
             "blue": "#0000ff", "highlight": "#00ff00"},
    "light": {"background": "#ffffff", "foreground": "#000000", "red": "#cc0000",
              "blue": "#0000cc", "highlight": "#00cc00"},
}


@pytest.fixture(scope="module")
def palette_map() -> dict:
    return patch_vsc.build_palette_map(PALETTE)


def test_a_hex_becomes_the_nearest_palette_colour(palette_map: dict) -> None:
    assert patch_vsc.closest_color("#fe0101", palette_map["dark"]) == "#ff0000"
    assert patch_vsc.closest_color("#010199", palette_map["dark"]) == "#0000ff"


def test_alpha_survives_the_match(palette_map: dict) -> None:
    """VSCode writes eight-digit hex for translucent surfaces; dropping the alpha would
    turn a wash over the editor into a solid block."""
    assert patch_vsc.closest_color("#fe010180", palette_map["dark"]) == "#ff000080"


def test_a_highlight_background_never_matches_the_editor_background(palette_map: dict) -> None:
    """The recorded bug: nearest-neighbour made selections invisible."""
    nearly_background = {"editor.selectionBackground": "#010101"}
    replaced = patch_vsc.dict_replace_value(nearly_background, palette_map["dark"])
    assert replaced["editor.selectionBackground"] != "#000000"


def test_an_ordinary_background_still_matches_the_background(palette_map: dict) -> None:
    """The exclusion is scoped to highlight-ish keys; widening it would flatten the theme."""
    replaced = patch_vsc.dict_replace_value({"editor.background": "#010101"}, palette_map["dark"])
    assert replaced["editor.background"] == "#000000"


@pytest.mark.parametrize(
    "key",
    ["editor.selectionBackground", "list.hoverBackground", "editor.focusedStackFrameHighlightBackground",
     "list.dropBackground", "editor.findMatchBackground", "editor.rangeHighlightBackground"],
)
def test_every_highlight_marker_excludes_the_background(key: str) -> None:
    assert patch_vsc._excludes_background(key)


@pytest.mark.parametrize("key", ["editor.background", "sideBar.background", None, "", "editor.foreground"])
def test_nothing_else_excludes_it(key: str | None) -> None:
    assert not patch_vsc._excludes_background(key)


def test_replacement_reaches_into_nested_lists_and_dicts(palette_map: dict) -> None:
    """Token colours are a list of dicts of dicts; a shallow walk would miss most of a theme."""
    theme = {"tokenColors": [{"settings": {"foreground": "#fe0101"}}]}
    replaced = patch_vsc.dict_replace_value(theme, palette_map["dark"])
    assert replaced["tokenColors"][0]["settings"]["foreground"] == "#ff0000"


def test_non_colour_values_pass_through_untouched(palette_map: dict) -> None:
    theme = {"name": "dot files", "semanticHighlighting": True, "version": 3, "scope": "#notahex"}
    assert patch_vsc.dict_replace_value(theme, palette_map["dark"]) == theme


def test_build_themes_names_both_modes(palette_map: dict) -> None:
    defaults = {"dark": {"colors": {}}, "light": {"colors": {}}}
    themes = patch_vsc.build_themes(defaults, palette_map, "nearest_neighbor")
    assert themes["dark"]["name"] == "dot files (dark)"
    assert themes["light"]["name"] == "dot files (light)"


def test_nearest_neighbour_maps_each_mode_against_its_own_palette(palette_map: dict) -> None:
    defaults = {"dark": {"colors": {"editor.foreground": "#fe0101"}},
                "light": {"colors": {"editor.foreground": "#fe0101"}}}
    themes = patch_vsc.build_themes(defaults, palette_map, "nearest_neighbor")
    assert themes["dark"]["colors"]["editor.foreground"] == "#ff0000"   # the dark red
    assert themes["light"]["colors"]["editor.foreground"] == "#cc0000"  # the light one


def test_reference_writes_the_dark_value_for_whatever_the_light_palette_matched(
    palette_map: dict,
) -> None:
    """The documented difference between the two methods, and the only thing that separates
    them: the light theme still *matches* against the light palette."""
    defaults = {"dark": {"colors": {}}, "light": {"colors": {"editor.foreground": "#fe0101"}}}
    themes = patch_vsc.build_themes(defaults, palette_map, "reference")
    assert themes["light"]["colors"]["editor.foreground"] == "#ff0000"


def test_the_default_themes_this_patcher_recolours_are_in_the_repository() -> None:
    """build_themes is only meaningful against the stock themes; a rename would strand it."""
    themes = patch_vsc.load_default_themes("configuration/vscode")
    assert set(themes) == set(patch_vsc.MODES)
    assert themes["dark"]["colors"], "the stock dark theme carries no colours"
