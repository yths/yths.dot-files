"""``setup.toml``: the one file a reader edits, and everything that reads it."""

import json
import shutil
import subprocess
import sys
import textwrap
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


def test_every_recorded_import_resolves_here() -> None:
    # The development machine has the packages, so the preflight bootstrap.sh runs before
    # install.py has nothing to report; what this checks is that the check itself is sound.
    assert list_dependencies.missing_imports() == []


def test_a_missing_import_is_named_with_its_package(monkeypatch: pytest.MonkeyPatch) -> None:
    real = list_dependencies.importlib.util.find_spec
    monkeypatch.setattr(
        list_dependencies.importlib.util, "find_spec",
        lambda name, *a: None if name == "cairo" else real(name, *a),
    )
    assert list_dependencies.missing_imports() == [("cairo", "python-pycairo")]


def test_a_missing_dependency_is_not_reported_as_a_missing_patcher() -> None:
    # The orchestrator's import guard exists for running it as a script. With cairo absent it
    # used to take that branch too and fail on its first name -- "No module named
    # 'patch_dunst'" -- leaving the dependency that was actually missing two tracebacks up.
    probe = textwrap.dedent(f"""
        import builtins, sys
        sys.path.insert(0, {str(Path(utils.REPOSITORY_ROOT))!r})
        real = builtins.__import__
        def fake(name, *args, **kwargs):
            if name == "cairo":
                raise ModuleNotFoundError("No module named 'cairo'", name="cairo")
            return real(name, *args, **kwargs)
        builtins.__import__ = fake
        try:
            import helper.patch_configurations
        except ModuleNotFoundError as error:
            print(error.name)
    """)
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=False,
    )
    assert result.stdout.strip() == "cairo", result.stderr


# packages/<pkgname>/PKGBUILD: the directory name is the contract bootstrap.sh relies on.
def test_each_repository_package_is_named_for_what_it_builds() -> None:
    directories = list_dependencies.repository_packages()
    assert directories, "packages/ holds nothing; the bootstrap loop would be dead code"
    if shutil.which("bash") is None:
        pytest.skip("bash is needed to evaluate a PKGBUILD")
    for name in directories:
        pkgbuild = Path(utils.REPOSITORY_ROOT) / "packages" / name / "PKGBUILD"
        declared = subprocess.run(
            ["bash", "-c", 'source "$1" && printf %s "$pkgname"', "_", str(pkgbuild)],
            capture_output=True, text=True, check=True,
        ).stdout
        assert declared == name, f"packages/{name}/ builds {declared!r}"


def test_a_repository_package_is_in_no_setup_group(setup: dict) -> None:
    # Listed in both, yay would try the broken AUR build first and fail the bootstrap there.
    listed = {name for group in setup["packages"].values() for name in group}
    assert not (listed & list_dependencies.repository_packages())


def test_the_colour_package_carries_its_hidden_dependency() -> None:
    pkgbuild = (
        Path(utils.REPOSITORY_ROOT) / "packages" / "python-colour-science" / "PKGBUILD"
    ).read_text()
    depends = next(line for line in pkgbuild.splitlines() if line.startswith("depends="))
    assert "openimageio" in depends
    assert "not test_write_spectral_image_Fichet2021" in pkgbuild
