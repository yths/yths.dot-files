"""``setup.toml``: the one file a reader edits, and everything that reads it."""

import json
from pathlib import Path

import list_dependencies
import pytest
import utils


@pytest.fixture(scope="module")
def setup() -> dict:
    return utils.read_setup()


def test_setup_parses_and_has_the_sections_everything_reads(setup: dict) -> None:
    assert set(setup) >= {"desktop", "state", "credentials", "packages"}


def test_the_configured_theme_is_one_that_ships(setup: dict) -> None:
    # An unknown name here sends install.py to sys.exit on a fresh machine, after the user
    # has already waited for the package install.
    configured = setup["desktop"]["theme"]
    if not configured:
        return
    bundles = (Path(utils.REPOSITORY_ROOT) / "assets").glob("*/config.json")
    names = {json.loads(path.read_text())["name"] for path in bundles}
    assert configured in names, f"setup.toml names {configured!r}; bundles are {sorted(names)}"


def test_the_configured_state_matches_the_documented_schema(setup: dict) -> None:
    assert set(setup["state"]) == {"theme", "condition", "theme_mode", "audio_mode"}
    assert setup["state"]["theme"] in {"light", "dark"}
    assert setup["state"]["condition"] in {"normal", "urgent"}
    assert setup["state"]["theme_mode"] in {"automatic", "manual"}
    assert setup["state"]["audio_mode"] in {"automatic", "manual"}


def test_package_groups_hold_plain_strings(setup: dict) -> None:
    for group, names in setup["packages"].items():
        assert names, f"[packages] {group} is empty; delete it rather than leaving it"
        assert all(isinstance(name, str) and name for name in names), group


def test_no_package_is_listed_twice_across_groups(setup: dict) -> None:
    # bootstrap.sh de-duplicates, but a name in two groups means one of them is wrong about
    # what stops working without it.
    seen: dict[str, str] = {}
    for group, names in setup["packages"].items():
        for name in names:
            assert name not in seen, f"{name} is in both {seen[name]} and {group}"
            seen[name] = group


# The point of consolidating: a dependency added to the code has to reach a fresh machine.
def test_every_dependency_is_installed_by_the_bootstrap() -> None:
    assert list_dependencies.mismatches(list_dependencies.third_party_imports()) == []


def test_a_dependency_missing_from_setup_is_reported(tmp_path: Path) -> None:
    imports = {"toml": ["helper/patch_starship.py"]}
    package, _ = list_dependencies.ARCH_PACKAGES["toml"]
    installed = list_dependencies.installed_packages()
    assert package in installed, "precondition: the real setup.toml installs it"
    # Simulate it being dropped from setup.toml.
    original = list_dependencies.installed_packages
    list_dependencies.installed_packages = lambda: installed - {package}
    try:
        problems = list_dependencies.mismatches(imports)
    finally:
        list_dependencies.installed_packages = original
    assert any("never installs it" in problem for problem in problems)


def test_read_setup_accepts_an_explicit_path(tmp_path: Path) -> None:
    path = tmp_path / "setup.toml"
    path.write_text('[desktop]\ntheme = "x"\n')
    assert utils.read_setup(str(path))["desktop"]["theme"] == "x"


def test_the_development_group_is_not_needed_to_run_the_desktop(setup: dict) -> None:
    # bootstrap.sh installs it only with --dev; nothing in the running desktop imports it.
    recorded = {package for package, _ in list_dependencies.ARCH_PACKAGES.values()}
    assert not (set(setup["packages"]["development"]) & recorded)


def test_bootstrap_reads_the_same_file() -> None:
    script = (Path(utils.REPOSITORY_ROOT) / "bootstrap.sh").read_text()
    assert "setup.toml" in script, "the script must not carry a package list of its own"
    for group in ("core", "boot", "backend", "python", "optional"):
        assert group in script, f"bootstrap.sh installs no {group} group"
