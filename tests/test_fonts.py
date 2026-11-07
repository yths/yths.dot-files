"""The theme's font: the bundle names it, the machine may lack it, setup.toml catches it."""

import json
import re
from pathlib import Path

import fonts
import pytest
import utils

SETUP = {"desktop": {"fallback_font_family": "Fallback NF", "fallback_font_package": "ttf-x"}}
BUNDLE = {"family": "Bundled Font", "size": 11}


def test_the_bundle_font_is_used_when_the_machine_has_it() -> None:
    assert fonts.resolve(BUNDLE, SETUP, families={"Bundled Font"}) == BUNDLE


def test_a_missing_font_falls_back_at_the_bundle_size() -> None:
    resolved = fonts.resolve(BUNDLE, SETUP, families={"Something Else"})
    assert resolved == {"family": "Fallback NF", "size": 11}


def test_a_bundle_with_no_font_gets_the_fallback() -> None:
    assert fonts.resolve(None, SETUP, families=set()) == {
        "family": "Fallback NF", "size": fonts.DEFAULT_SIZE
    }


def test_a_machine_without_fontconfig_is_trusted(monkeypatch: pytest.MonkeyPatch) -> None:
    # No fc-list, no check: the bundle's font goes in as declared, and fontconfig substitutes
    # at render time if it has to. Falling back blind would hide a font that is there.
    monkeypatch.setattr(fonts, "installed_families", lambda: None)
    assert fonts.resolve(BUNDLE, SETUP) == BUNDLE


def test_every_fontconfig_alias_is_collected(monkeypatch: pytest.MonkeyPatch) -> None:
    class Result:
        returncode = 0
        stdout = "Iosevka Nerd Font,Iosevka NF\nAtkynsonMono Nerd Font,AtkynsonMono NF\n"

    monkeypatch.setattr(fonts.subprocess, "run", lambda *a, **k: Result())
    assert fonts.installed_families() == {
        "Iosevka Nerd Font", "Iosevka NF", "AtkynsonMono Nerd Font", "AtkynsonMono NF"
    }


def test_a_plain_family_is_installed_as_its_nerd_font_build() -> None:
    # The bar needs the private-use glyphs; the Nerd Font build is the same face with them.
    plain = {"family": "Atkinson Hyperlegible Mono", "size": 12}
    assert fonts.package_for(plain) == "otf-atkinsonhyperlegiblemono-nerd"
    assert fonts.resolve(plain, SETUP, families={"Atkinson Mono NF"}) == {
        "family": "Atkinson Mono NF", "size": 12
    }
    # Only the plain family present: that is still not the font the bar needs, so fall back.
    assert fonts.resolve(plain, SETUP, families={"Atkinson Hyperlegible Mono"}) == {
        "family": "Fallback NF", "size": 12
    }


def test_legacy_atkinson_bundle_alias_matches_the_installed_family() -> None:
    bundle_font = {"family": "AtkynsonMono NF", "size": 14}
    assert fonts.resolve(bundle_font, SETUP, families={"Atkinson Mono NF"}) == {
        "family": "Atkinson Mono NF", "size": 14
    }
    assert fonts.package_for(bundle_font) == "otf-atkinsonhyperlegiblemono-nerd"


def test_every_nerd_font_build_has_a_package() -> None:
    for build in set(fonts.NERD_FONT_BUILDS.values()):
        assert build in fonts.FONT_PACKAGES, build


def test_the_bundle_may_name_its_own_package() -> None:
    assert fonts.package_for({"family": "Iosevka NF", "package": "ttf-mine"}) == "ttf-mine"
    assert fonts.package_for({"family": "Iosevka NF"}) == "ttf-iosevka-nerd"
    assert fonts.package_for({"family": "Nobody Has Heard Of This"}) is None
    assert fonts.package_for(None) is None


def test_the_fallback_is_a_nerd_font_with_a_known_package() -> None:
    # The bar draws from the private use area, so whatever catches a failed font install
    # has to carry those glyphs; and the package has to be the one that provides the family.
    desktop = utils.read_setup()["desktop"]
    assert desktop["fallback_font_family"].endswith((" NF", " Nerd Font"))
    assert fonts.FONT_PACKAGES[desktop["fallback_font_family"]] == desktop["fallback_font_package"]


def test_the_shipped_bundle_font_has_a_package() -> None:
    # A fresh machine installs the configured theme's font through this table; a tracked
    # bundle it cannot place would install the fallback on every machine and never say so.
    for bundle in utils.tracked_bundles():
        manifest = json.loads((Path(utils.REPOSITORY_ROOT) / "assets" / bundle / "config.json").read_text())
        assert fonts.package_for(manifest["font"]), f"{bundle} names a font with no package"


def test_bootstrap_installs_the_fallback_before_the_theme_font() -> None:
    script = (Path(utils.REPOSITORY_ROOT) / "bootstrap.sh").read_text()
    assert "fallback_font_package" in script, "the fallback must go in with the packages"
    theme_font = script.index("helper/fonts.py")
    assert script.index("fallback_font_package") < theme_font
    # The theme's font is the one install that may fail without stopping the bootstrap.
    assert re.search(r'yay -S --needed --noconfirm "\$theme_font"\s*\\?\s*\|\|', script)


def test_bootstrap_builds_the_greeter_from_the_repository() -> None:
    script = (Path(utils.REPOSITORY_ROOT) / "bootstrap.sh").read_text()
    assert "/packages/*/" in script
    assert "makepkg -si" in script
    assert (Path(utils.REPOSITORY_ROOT) / "packages" / "nody-greeter" / "PKGBUILD").is_file()
    packages = utils.read_setup()["packages"]
    assert not any("nody-greeter" in group for group in packages.values()), (
        "nody-greeter comes from the patched PKGBUILD, not the AUR"
    )
