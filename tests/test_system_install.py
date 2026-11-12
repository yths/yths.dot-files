"""`install.py --system`: the login screen and boot splash, with root asked for once, first.

A theme switch used to be three commands, the second and third each needing root. These
hold the order that makes one command safe: root before anything changes, so a refused
password leaves the machine as it was; the system patchers only after the desktop switched;
and one failing patcher not stopping the other.
"""

import subprocess

import pytest
import utils

import install
from helper import patch_configurations

# ------------------------------------------------------------------------- authenticate


def test_sudo_is_asked_once_and_then_used_without_asking(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(utils, "root_prefix", lambda **_kwargs: ["sudo"])
    monkeypatch.setattr(
        utils.subprocess, "run",
        lambda argv, **_kwargs: calls.append(argv) or subprocess.CompletedProcess(argv, 0),
    )
    assert utils.authenticate() == ["sudo", "-n"]
    assert calls == [["sudo", "-v"]]


def test_a_refused_password_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(utils, "root_prefix", lambda **_kwargs: ["sudo"])
    monkeypatch.setattr(
        utils.subprocess, "run", lambda argv, **_kwargs: subprocess.CompletedProcess(argv, 1)
    )
    assert utils.authenticate() is None


def test_already_root_or_cached_needs_no_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    for prefix in ([], ["sudo", "-n"]):
        monkeypatch.setattr(utils, "root_prefix", lambda prefix=prefix, **_kwargs: prefix)
        assert utils.authenticate() == prefix


# ------------------------------------------------------------------------- the registry


def test_one_failing_system_patcher_does_not_stop_the_other(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ran = []

    def raises(_configuration: dict, *, prompt: bool) -> bool:
        ran.append("login screen")
        raise RuntimeError("greeter")

    def succeeds(_configuration: dict, *, prompt: bool) -> bool:
        ran.append(f"boot splash, prompt={prompt}")
        return True

    monkeypatch.setattr(
        patch_configurations, "SYSTEM_PATCHERS",
        (("login screen", raises), ("boot splash", succeeds)),
    )
    assert patch_configurations.install_system({}, prompt=True) == ["login screen"]
    assert ran == ["login screen", "boot splash, prompt=True"]


def test_a_patcher_reporting_failure_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        patch_configurations, "SYSTEM_PATCHERS", (("boot splash", lambda _c, **_k: False),)
    )
    assert patch_configurations.install_system({}) == ["boot splash"]


def test_both_system_surfaces_are_registered() -> None:
    assert [name for name, _ in patch_configurations.SYSTEM_PATCHERS] == [
        "login screen", "boot splash",
    ]


# ------------------------------------------------------------------------- install.py


@pytest.fixture
def steps(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record the order of the installer's steps, with each one stubbed."""
    order: list[str] = []
    monkeypatch.setattr(install, "enable_git_hooks", lambda: None)
    monkeypatch.setattr(install, "authenticate", lambda: order.append("authenticate") or [])
    monkeypatch.setattr(
        install, "run_migration",
        lambda *_args, **_kwargs: order.append("migrate") or 0,
    )
    monkeypatch.setattr(
        install, "install_system_surfaces", lambda: order.append("system") or 0
    )
    return order


def test_root_is_asked_for_before_the_migration(steps: list[str]) -> None:
    assert install.main(["--migrate", "--theme", "x", "--system"]) == 0
    assert steps == ["authenticate", "migrate", "system"]


def test_a_refused_password_changes_nothing(
    steps: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(install, "authenticate", lambda: steps.append("authenticate") and None)
    assert install.main(["--migrate", "--system"]) == 1
    assert steps == ["authenticate"], "neither the migration nor the system step ran"


def test_a_failed_migration_installs_nothing_system_wide(
    steps: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        install, "run_migration", lambda *_a, **_k: steps.append("migrate") or 1
    )
    assert install.main(["--migrate", "--system"]) == 1
    assert steps == ["authenticate", "migrate"]


def test_without_system_no_root_is_asked_for(steps: list[str]) -> None:
    assert install.main(["--migrate"]) == 0
    assert steps == ["migrate"]
