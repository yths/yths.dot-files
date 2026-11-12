"""Theme-bundle discovery: the directory name is the identity.

`docs/notes.md` states that a bundle's directory name and its manifest's `name` are written
from one value, "so a bundle can be identified from a file listing rather than by opening the
JSON inside it". `install.py` used to key on the manifest, which made that untrue: a directory
`my-bundle` whose manifest said `something-else` answered `--theme my-bundle` with "unknown
theme" while sitting in plain sight.

The disagreement is not cosmetic. `patch_plymouth.theme_source` looks for a preset's boot
splash at `configuration/plymouth/themes/<manifest name>`, so a bundle installed from a
directory that says something else ships no splash and says nothing about it.
"""

import json
import pathlib

import patch_plymouth
import pytest
from utils import read_setup

import install


def bundle(root: pathlib.Path, directory: str, declared: str | None = None) -> pathlib.Path:
    """A bundle directory whose manifest names it ``declared`` (its own name by default)."""
    path = root / directory
    path.mkdir(parents=True)
    manifest = {"name": directory if declared is None else declared}
    (path / "config.json").write_text(json.dumps(manifest))
    return path


def test_a_bundle_is_found_by_its_directory_name(tmp_path: pathlib.Path) -> None:
    bundle(tmp_path, "my-bundle")
    assert set(install.discover_themes(str(tmp_path))) == {"my-bundle"}


def test_several_bundles_are_all_found(tmp_path: pathlib.Path) -> None:
    bundle(tmp_path, "default")
    bundle(tmp_path, "somebody-elses")
    assert sorted(install.discover_themes(str(tmp_path))) == ["default", "somebody-elses"]


def test_a_directory_without_a_manifest_is_not_a_bundle(tmp_path: pathlib.Path) -> None:
    """Discovery is by the presence of a config.json, which is what lets an ignored bundle
    sit beside the tracked one."""
    (tmp_path / "wallpapers").mkdir()
    bundle(tmp_path, "default")
    assert set(install.discover_themes(str(tmp_path))) == {"default"}


def test_a_manifest_that_disagrees_is_refused(tmp_path: pathlib.Path) -> None:
    """The regression, and the reason it matters is in the message."""
    bundle(tmp_path, "my-bundle", declared="something-else")
    with pytest.raises(install.InconsistentBundle, match="something-else"):
        install.discover_themes(str(tmp_path))


def test_the_refusal_names_the_directory_to_fix(tmp_path: pathlib.Path) -> None:
    bundle(tmp_path, "my-bundle", declared="something-else")
    with pytest.raises(install.InconsistentBundle) as raised:
        install.discover_themes(str(tmp_path))
    assert "assets/my-bundle/" in str(raised.value)
    assert "Rename the directory" in str(raised.value)


def test_a_manifest_with_no_name_at_all_is_refused(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "my-bundle"
    path.mkdir()
    (path / "config.json").write_text("{}")
    with pytest.raises(install.InconsistentBundle):
        install.discover_themes(str(tmp_path))


def test_one_bad_bundle_does_not_hide_the_good_ones_silently(tmp_path: pathlib.Path) -> None:
    """Refusing outright beats installing the rest and leaving one mysteriously absent."""
    bundle(tmp_path, "default")
    bundle(tmp_path, "broken", declared="other")
    with pytest.raises(install.InconsistentBundle):
        install.discover_themes(str(tmp_path))


def test_the_shipped_bundle_is_consistent() -> None:
    """The contract, against the bundle this repository actually tracks."""
    assert install.discover_themes("assets") == {"default": "assets/default"}


def test_the_configured_theme_is_a_bundle_that_exists() -> None:
    """setup.toml names a theme; discovery has to be able to find it."""
    assert read_setup()["desktop"]["theme"] in install.discover_themes("assets")


def test_the_shipped_bundle_has_a_boot_splash_where_plymouth_looks() -> None:
    """The consequence the check exists to prevent, asserted directly."""
    name = next(iter(install.discover_themes("assets")))
    assert patch_plymouth.theme_source({"name": name}) is not None
