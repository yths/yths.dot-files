"""The symbol and string vocabulary, and the two properties that make it worth having.

The first is that the defaults are ASCII. That is the whole point: a machine whose font has
no private use area gets a readable desktop rather than a row of tofu, and nothing here asks
the font what it can draw -- so the fallback has to be the default rather than something
chosen at install time.

The second is that an override is partial. A bundle that wants one glyph changed must not
have to restate the other eighty, and must not blank them by omission. That rule is older
than this module: `patch_web_greeter` has depended on it since a login theme could pin its
font size without also naming the family.
"""

import json
import pathlib
import pickle

import pytest
import symbols
from utils import merge_overrides

import install

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


# The reason the module exists. A default that needs a Nerd Font is not a fallback.
@pytest.mark.parametrize("vocabulary", [symbols.SYMBOLS, symbols.STRINGS])
def test_every_default_is_ascii(vocabulary: dict) -> None:
    for key, value in vocabulary.items():
        rungs = value if isinstance(value, tuple) else (value,)
        for rung in rungs:
            assert rung.isascii(), f"{key} defaults to {rung!r}, which needs a font to draw"


def test_every_default_is_printable() -> None:
    """A control character renders as nothing, which is worse than a wrong glyph."""
    for key, value in symbols.SYMBOLS.items():
        rungs = value if isinstance(value, tuple) else (value,)
        for rung in rungs:
            assert rung.isprintable(), f"{key} defaults to an unprintable {rung!r}"


# A ramp is indexed by a level the caller computed, so the wrong length is an IndexError
# inside a widget's poll() -- which takes the whole cell down rather than drawing badly.
def test_every_ramp_has_the_length_its_consumers_index() -> None:
    assert not symbols.malformed(symbols.SYMBOLS)
    for key, expected in symbols.RAMP_LENGTHS.items():
        assert isinstance(symbols.SYMBOLS[key], tuple), f"{key} is a ramp and must be a tuple"
        assert len(symbols.SYMBOLS[key]) == expected


def test_a_ramp_declared_in_lengths_exists_in_the_vocabulary() -> None:
    assert set(symbols.RAMP_LENGTHS) <= set(symbols.SYMBOLS)


# ------------------------------------------------------------------------- resolution


def test_an_override_replaces_only_what_it_names() -> None:
    resolved, _ = symbols.resolve({"symbols": {"vpn.on": "VPN!"}})
    assert resolved["vpn.on"] == "VPN!"
    assert resolved["vpn.off"] == symbols.SYMBOLS["vpn.off"], "an override must not clear the rest"
    assert len(resolved) == len(symbols.SYMBOLS)


def test_a_configuration_with_neither_block_still_resolves() -> None:
    """A ~/.config/config.json written before this existed has to keep working."""
    resolved, strings = symbols.resolve({})
    assert resolved == symbols.SYMBOLS
    assert strings == symbols.STRINGS


def test_a_null_block_is_treated_as_absent() -> None:
    resolved, strings = symbols.resolve({"symbols": None, "strings": None})
    assert resolved == symbols.SYMBOLS
    assert strings == symbols.STRINGS


# JSON has no tuples, so a bundle's ramp arrives as a list. A widget that sorted or sliced one
# in place would change the vocabulary for every later caller in the same process.
def test_a_ramp_from_a_bundle_becomes_an_immutable_tuple() -> None:
    resolved, _ = symbols.resolve({"symbols": {"meter.ramp": list("abcdefgh")}})
    assert resolved["meter.ramp"] == tuple("abcdefgh")
    assert isinstance(resolved["meter.ramp"], tuple)


def test_resolving_does_not_mutate_the_defaults() -> None:
    before = dict(symbols.SYMBOLS)
    symbols.resolve({"symbols": {"vpn.on": "changed"}})
    assert before == symbols.SYMBOLS


def test_merge_overrides_leaves_its_base_alone() -> None:
    base = {"a": 1, "b": 2}
    assert merge_overrides(base, {"b": 3}) == {"a": 1, "b": 3}
    assert base == {"a": 1, "b": 2}


# ------------------------------------------------------------------------- validation


def test_undeclared_names_an_override_nothing_reads() -> None:
    """Overriding a key no default declares is silent: the bundle looks set, nothing moves."""
    assert symbols.undeclared({"symbols": {"vpn.on": "x"}}) == []
    assert symbols.undeclared({"symbols": {"nonesuch": "x"}}) == ["nonesuch"]
    assert symbols.undeclared({"strings": {"also.nonesuch": "x"}}) == ["also.nonesuch"]


def test_malformed_names_a_ramp_of_the_wrong_length() -> None:
    assert symbols.malformed({"meter.ramp": tuple("abc")}) == [
        "meter.ramp: 3 rungs, expected 8"
    ]
    assert symbols.malformed({"meter.ramp": tuple("abcdefgh")}) == []


# ------------------------------------------------------------- the installed configuration


def test_the_installer_merges_both_blocks_over_the_defaults(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End to end through assemble_configuration, which is where a bundle's blocks land."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "config.json").write_text(
        json.dumps({"name": "bundle", "symbols": {"vpn.on": "VPN"}})
    )
    monkeypatch.setattr(install.helper.screen_configuration, "get", dict)
    palette = tmp_path / ".config" / "palette.pkl"
    palette.parent.mkdir(parents=True)
    palette.write_bytes(pickle.dumps({"dark": {}, "light": {}}))
    monkeypatch.setenv("HOME", str(tmp_path))

    configuration = install.assemble_configuration(str(bundle), {})
    assert configuration["symbols"]["vpn.on"] == "VPN"
    assert configuration["symbols"]["vpn.off"] == symbols.SYMBOLS["vpn.off"]
    assert configuration["strings"] == symbols.STRINGS


def test_the_shipped_bundle_declares_nothing_the_vocabulary_has_not() -> None:
    """A typo in the tracked bundle would be a glyph that silently never appears."""
    for manifest in sorted(REPO_ROOT.glob("assets/*/config.json")):
        bundle = json.loads(manifest.read_text())
        assert symbols.undeclared(bundle) == [], f"{manifest}: overrides nothing declares"
        assert symbols.malformed(bundle.get("symbols") or {}) == [], f"{manifest}: bad ramp"
