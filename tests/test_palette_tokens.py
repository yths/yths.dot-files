"""The palette's vocabulary, and what a bundle from before its newest tokens is given.

`palette.json` is written by chromalytica and read here, and nothing but the token names and
their order ties the two together. chromalytica holds the same tuple and tests it against the
bundle this repository tracks; these hold that bundle to the tuple from this side, so neither
repository can move the vocabulary alone.
"""

import json
import pathlib
import re

import color_match
import palette_tokens
import pytest
import utils

ASSETS = pathlib.Path(utils.REPOSITORY_ROOT) / "assets"

LEGACY = {
    "light": {"background": "#ffffff", "neutral": "#7f7f7f", "foreground": "#3f3f3f"},
    "dark": {"background": "#000000", "neutral": "#808080", "foreground": "#c0c0c0"},
}


def _palette(bundle: str) -> dict[str, dict[str, str]]:
    return json.loads((ASSETS / bundle / "palette.json").read_text(encoding="utf-8"))


# The order is part of the format: an exported palette is diffed against the one it replaces,
# and chromalytica's own contract test compares the two key sequences.
@pytest.mark.parametrize("bundle", utils.tracked_bundles())
def test_a_tracked_bundle_holds_exactly_the_vocabulary_in_order(bundle: str) -> None:
    palette = _palette(bundle)
    assert list(palette) == ["light", "dark"]
    for mode, colours in palette.items():
        assert tuple(colours) == palette_tokens.TOKENS, mode
        assert all(re.fullmatch(r"#[0-9a-f]{6}", value) for value in colours.values()), mode


def test_the_vocabulary_names_each_token_once() -> None:
    assert len(set(palette_tokens.TOKENS)) == len(palette_tokens.TOKENS) == 24


def test_every_grey_group_is_part_of_the_vocabulary() -> None:
    for group in (palette_tokens.GREYS, palette_tokens.TEXT_GREYS,
                  palette_tokens.SURFACE_GREYS, palette_tokens.DERIVED):
        assert set(group) <= set(palette_tokens.TOKENS)
    assert not palette_tokens.TEXT_GREYS & palette_tokens.SURFACE_GREYS


# ------------------------------------------------------------- a bundle that predates them


def test_a_bundle_without_the_newest_tokens_is_given_them() -> None:
    completed = palette_tokens.complete(LEGACY)
    assert completed["light"]["surface"] == "#dfdfdf"            # a quarter of the way
    assert completed["light"]["surface_variant"] == "#bfbfbf"    # half of the way
    assert completed["light"]["foreground_muted"] == "#5f5f5f"   # between border and text
    assert completed["dark"]["surface"] == "#202020"
    assert "surface" not in LEGACY["light"], "the bundle's own palette is left as it was"


# The generator picks these against the whole grid; a mix of two neighbours is a stand-in for
# that and must never overwrite it.
def test_a_token_the_bundle_carries_is_kept() -> None:
    palette = {"light": {**LEGACY["light"], "surface": "#123456"}}
    assert palette_tokens.complete(palette)["light"]["surface"] == "#123456"


def test_only_what_is_missing_is_reported_as_derived() -> None:
    assert palette_tokens.derived(LEGACY) == ["surface", "surface_variant", "foreground_muted"]
    assert palette_tokens.derived(palette_tokens.complete(LEGACY)) == []
    one_mode_short = {"light": palette_tokens.complete(LEGACY)["light"], "dark": LEGACY["dark"]}
    assert "surface" in palette_tokens.derived(one_mode_short)


# A mode without the greys to mix from is left without the token, so the consumer fails on
# the name it asked for rather than this raising on one it never mentioned.
def test_a_mode_that_cannot_be_completed_is_left_alone() -> None:
    assert palette_tokens.complete({"light": {"background": "#ffffff"}}) == {
        "light": {"background": "#ffffff"}
    }


def test_a_mix_is_weighted_channel_by_channel() -> None:
    assert palette_tokens.mix("#000000", "#ffffff", 0.5) == "#808080"
    assert palette_tokens.mix("#102030", "#102030", 0.25) == "#102030"
    assert palette_tokens.mix("#000000", "#ff8000", 0) == "#000000"


# ------------------------------------------------ what the greys have to be, in every bundle


def _bundle_modes() -> list[tuple[str, dict[str, str]]]:
    """Every bundle on this machine, completed the way the installer completes it."""
    found = []
    for path in sorted(ASSETS.glob("*/palette.json")):
        palette = palette_tokens.complete(json.loads(path.read_text(encoding="utf-8")))
        found += [(f"{path.parent.name}-{mode}", colours) for mode, colours in palette.items()]
    return found


# Muted text is still text. Whether a bundle ships the token or is given a stand-in, it has
# to clear body-text contrast on the background, or dunst's low-urgency titles do not read.
@pytest.mark.parametrize(("name", "colours"), _bundle_modes(), ids=lambda value: str(value)[:24])
def test_muted_text_reads_on_the_background(name: str, colours: dict[str, str]) -> None:
    ratio = color_match.contrast(colours["foreground_muted"], colours["background"])
    assert ratio >= color_match.MIN_TEXT_CONTRAST, f"{name}: {ratio:.2f}:1"


# The two surfaces step away from the background in order, and stop short of the border grey.
@pytest.mark.parametrize(("name", "colours"), _bundle_modes(), ids=lambda value: str(value)[:24])
def test_the_surfaces_step_away_from_the_background(name: str, colours: dict[str, str]) -> None:
    steps = [
        color_match.contrast(colours[token], colours["background"])
        for token in ("surface", "surface_variant", "neutral")
    ]
    assert 1 < steps[0] < steps[1] < steps[2], f"{name}: {steps}"
