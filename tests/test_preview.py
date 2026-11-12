"""The README's generated summary and the preview rendered from the theme."""

import ast
import pathlib
import pickle

import list_configured
import render_preview
import utils

REPO = pathlib.Path(utils.REPOSITORY_ROOT)


def test_the_application_list_comes_from_the_installer() -> None:
    # Derived, not repeated: adding an application to install.py is the only edit needed.
    applications = dict(list_configured.installed_applications())
    assert "qtile" in applications
    assert applications["kitty"] == "~/.config/kitty"


def test_every_installed_application_has_a_purpose_recorded() -> None:
    # A new entry in install.py with no purpose renders an empty cell, which reads as a bug.
    missing = [label for label, _ in list_configured.installed_applications()
               if label not in list_configured.PURPOSE]
    assert missing == [], f"add these to PURPOSE: {missing}"


def test_no_purpose_is_recorded_for_something_no_longer_installed() -> None:
    labels = {label for label, _ in list_configured.installed_applications()}
    assert set(list_configured.PURPOSE) <= labels


def test_the_generated_block_names_the_configured_theme() -> None:
    assert utils.read_setup()["desktop"]["theme"] in list_configured.generate_markdown()


# The preview must not be able to show anything that was on a screen. This is the property
# the whole approach rests on, so it is asserted rather than trusted to review.
def test_the_renderer_reads_only_the_theme_bundle() -> None:
    tree = ast.parse((REPO / "helper" / "render_preview.py").read_text())
    opened = [
        ast.unparse(node.args[0])
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "open" and node.args
    ]
    assert opened, "expected the renderer to read the palette"
    assert all("palette.pkl" in path or "DIGEST" in path for path in opened), opened


def test_the_renderer_touches_no_session_source() -> None:
    source = (REPO / "helper" / "render_preview.py").read_text()
    body = source.split('"""', 2)[2]        # skip the module docstring, which discusses them
    for forbidden in ("subprocess", "socket", "getuser", "gethostname", "environ",
                      "expanduser", "config.json"):
        assert forbidden not in body, f"the renderer reaches for {forbidden}"


def test_the_digest_covers_both_the_palette_and_the_font() -> None:
    palette = {"light": {"background": "#ffffff"}, "dark": {"background": "#000000"}}
    baseline = render_preview.palette_digest(palette, "Iosevka NF")
    assert baseline != render_preview.palette_digest(palette, "Other Font")
    changed = {"light": {"background": "#fffffe"}, "dark": {"background": "#000000"}}
    assert baseline != render_preview.palette_digest(changed, "Iosevka NF")
    assert baseline == render_preview.palette_digest(palette, "Iosevka NF"), "stable"


def test_the_committed_preview_matches_the_committed_palette() -> None:
    # The images are tracked, which is only defensible while they cannot fall behind.
    setup = utils.read_setup()
    with (REPO / "assets" / setup["desktop"]["theme"] / "palette.pkl").open("rb") as handle:
        palette = pickle.load(handle)
    expected = render_preview.palette_digest(palette, setup["desktop"]["font_family"])
    recorded = (REPO / "docs" / "preview" / "rendered-from.txt").read_text().strip()
    assert recorded == expected, "run `python helper/render_preview.py`"


def test_both_variants_are_present() -> None:
    for mode in ("light", "dark"):
        image = REPO / "docs" / "preview" / f"{mode}.png"
        assert image.is_file() and image.stat().st_size > 1000, mode
