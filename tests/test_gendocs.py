"""The commit gate's own checks. Nothing else tests the thing that tests everything.

The link check exists because a bulk replacement across ninety-five files tore a sentence in
half and left `](../nuunamnir/README.md)` with no opening bracket, pointing at a directory
the same commit deleted. It sat in the tree through a green gate, and an ordinary link
checker would have passed it too: with the bracket gone it is not a link, so there is nothing
to resolve.
"""

import datetime
import pathlib
import subprocess
import sys

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


# ------------------------------------------------- documentation past its verification date

TODAY = datetime.date(2026, 8, 30)


def test_a_recent_claim_is_not_reported(docs: pathlib.Path) -> None:
    (docs / "guide.md").write_text("> Last verified 2026-08-01 on Arch ISO 2026.08.01\n")
    assert gendocs.stale_verification_markers(TODAY) == []


def test_a_claim_past_the_interval_is_reported(docs: pathlib.Path) -> None:
    """docs/os-build.md's real date when this check was written: 106 days, one quarter past."""
    (docs / "guide.md").write_text("> Last verified 2026-05-16 on Arch ISO 2026.04.01\n")
    reported = gendocs.stale_verification_markers(TODAY)
    assert reported == ["guide.md — last verified 2026-05-16, 106 days ago"]


def test_the_boundary_is_not_reported(docs: pathlib.Path) -> None:
    edge = TODAY - gendocs.VERIFICATION_INTERVAL
    (docs / "guide.md").write_text(f"> Last verified {edge} on something\n")
    assert gendocs.stale_verification_markers(TODAY) == []


def test_a_document_without_a_claim_is_not_reported(docs: pathlib.Path) -> None:
    (docs / "notes.md").write_text("# Notes\n\nNothing is claimed here.\n")
    assert gendocs.stale_verification_markers(TODAY) == []


def test_an_unreadable_date_is_reported_rather_than_skipped(docs: pathlib.Path) -> None:
    """A marker that cannot be parsed is the one most likely to be quietly wrong."""
    (docs / "guide.md").write_text("> Last verified 2026-13-45 on something\n")
    assert gendocs.stale_verification_markers(TODAY) == [
        "guide.md — unreadable date '2026-13-45'"
    ]


def test_the_marker_is_only_recognised_as_a_blockquote(docs: pathlib.Path) -> None:
    """docs/style.md specifies the blockquote form; prose mentioning a date is not a claim."""
    (docs / "guide.md").write_text("We last verified 2020-01-01, roughly.\n")
    assert gendocs.stale_verification_markers(TODAY) == []


def test_staleness_is_a_warning_and_not_an_invariant() -> None:
    """Nobody can re-verify a bare-metal Arch install to satisfy a commit hook, and a gate
    that failed on a date would start refusing unrelated work overnight -- with editing the
    date as the only remedy, which teaches the marker to lie."""
    titles = [title for title, _, _ in gendocs.invariants()]
    assert not any("verified" in title.lower() for title in titles)


def test_the_gate_passes_while_the_real_documentation_is_stale() -> None:
    """End to end, against whatever the tree actually holds."""
    if not gendocs.stale_verification_markers():
        pytest.skip("nothing in the tree is past its verification date")
    result = subprocess.run(
        [sys.executable, "helper/gendocs.py", "--check"],
        cwd=gendocs.REPO_ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0
    assert "verification date" in result.stderr
