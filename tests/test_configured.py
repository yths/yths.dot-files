"""The README's generated summary of what the installer links into place."""

import list_configured
import utils


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
