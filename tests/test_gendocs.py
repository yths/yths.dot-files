"""The commit gate's own checks. Nothing else tests the thing that tests everything.

The link check exists because a bulk replacement across ninety-five files tore a sentence in
half and left `](../nuunamnir/README.md)` with no opening bracket, pointing at a directory
the same commit deleted. It sat in the tree through a green gate, and an ordinary link
checker would have passed it too: with the bracket gone it is not a link, so there is nothing
to resolve.
"""

import pathlib

import gendocs
import pytest


@pytest.fixture
def docs(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    monkeypatch.setattr(gendocs, "REPO_ROOT", tmp_path)
    return tmp_path


def test_a_resolving_link_is_not_reported(docs: pathlib.Path) -> None:
    (docs / "target.md").write_text("# Target\n")
    (docs / "index.md").write_text("See [the target](target.md).\n")
    assert gendocs.broken_documentation_links() == []


def test_a_dead_link_is_reported(docs: pathlib.Path) -> None:
    (docs / "index.md").write_text("See [the target](gone.md).\n")
    assert gendocs.broken_documentation_links() == ["index.md — gone.md"]


def test_a_link_that_lost_its_bracket_is_reported(docs: pathlib.Path) -> None:
    """The regression: not a broken link, damaged text, and reported by nothing else."""
    (docs / "target.md").write_text("# Target\n")
    (docs / "index.md").write_text("the theme this repository ships../target.md](target.md)\n")
    assert gendocs.broken_documentation_links() == [
        "index.md:1 — a link lost its opening bracket"
    ]


def test_an_anchor_is_checked_as_far_as_the_file(docs: pathlib.Path) -> None:
    (docs / "notes.md").write_text("# Notes\n")
    (docs / "index.md").write_text("[a](notes.md#palette-design) [b](gone.md#x)\n")
    assert gendocs.broken_documentation_links() == ["index.md — gone.md#x"]


def test_a_bare_anchor_needs_no_file(docs: pathlib.Path) -> None:
    (docs / "index.md").write_text("[back to the top](#top)\n")
    assert gendocs.broken_documentation_links() == []


def test_external_links_are_not_fetched(docs: pathlib.Path) -> None:
    """Reachability is somebody else's uptime, not a property of this commit."""
    (docs / "index.md").write_text(
        "[a](https://example.invalid/x) [b](http://x) [c](mailto:x@y.z)\n"
    )
    assert gendocs.broken_documentation_links() == []


def test_an_image_has_to_resolve_too(docs: pathlib.Path) -> None:
    (docs / "index.md").write_text("![preview](preview/light.png)\n")
    assert gendocs.broken_documentation_links() == ["index.md — preview/light.png"]


def test_links_in_subdirectories_resolve_from_their_own_file(docs: pathlib.Path) -> None:
    (docs / "notes.md").write_text("# Notes\n")
    nested = docs / "palettes" / "default"
    nested.mkdir(parents=True)
    (nested / "README.md").write_text("[up](../../notes.md) [sideways](../../missing.md)\n")
    assert gendocs.broken_documentation_links() == [
        "palettes/default/README.md — ../../missing.md"
    ]


def test_unmaintained_directories_are_skipped(docs: pathlib.Path) -> None:
    cache = docs / ".pytest_cache"
    cache.mkdir()
    (cache / "README.md").write_text("[dead](nowhere.md)\n")
    assert gendocs.broken_documentation_links() == []


def test_the_real_documentation_has_no_broken_links() -> None:
    """The check, against the tree it guards."""
    assert gendocs.broken_documentation_links() == []
