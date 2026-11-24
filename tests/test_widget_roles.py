"""Which palette token each cell of the bar reaches for, and that it is the one it names.

Three tokens ask for attention and they are not interchangeable (docs/palette-semantics.md):
``warning`` is an error state, ``highlight`` is what wants looking at now, ``notification``
is worth knowing and nothing to act on. The bar used all three loosely -- a tunnel being up
and a low battery were both drawn in ``warning``, and ``config.py`` handed the updates cell
``highlight`` under the name ``notification_color`` -- so a colour said nothing about what
kind of thing had happened.
"""

import ast
import pathlib
import subprocess
import types

import pytest
import shared.stream
import symbols
import utils
from widgets.bluetooth import WidgetBluetooth
from widgets.broadcast import WidgetBroadcast
from widgets.claude_usage import WidgetClaudeUsage
from widgets.power_supply import WidgetPowerSupply
from widgets.service_state import WidgetServiceState
from widgets.updates import WidgetUpdates
from widgets.vpn import WidgetVPN

QTILE = pathlib.Path(utils.REPOSITORY_ROOT) / "configuration" / "qtile"

HIGHLIGHT, NOTIFICATION, WARNING = "#111111", "#222222", "#333333"
ROLES = {"highlight_color": HIGHLIGHT, "notification_color": NOTIFICATION, "warning_color": WARNING}

#: The cells with a state that is an error rather than a level or a piece of news: the
#: backend being down, and a sign-in that stays broken until somebody signs in again.
REPORTS_AN_ERROR = {"service_state", "claude_usage"}


def _streamed(monkeypatch: pytest.MonkeyPatch, measurement: dict | None) -> None:
    monkeypatch.setattr(shared.stream, "read_measurement", lambda _r, _stream: measurement)


def _roles(widget_class: type) -> dict[str, str]:
    """The role colours this widget takes, and no others -- a role it does not use is not
    something its constructor should accept."""
    parameters = widget_class.__init__.__code__.co_varnames
    return {name: colour for name, colour in ROLES.items() if name in parameters}


# ------------------------------------------------------------------------- the wiring


def _role_keywords() -> list[tuple[str, str, int]]:
    """``(keyword, token, line)`` for every ``<role>_color=...palette...[token]`` in config.py."""
    tree = ast.parse((QTILE / "config.py").read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.keyword) or not (node.arg or "").endswith("_color"):
            continue
        value = node.value
        if isinstance(value, ast.Subscript) and isinstance(value.slice, ast.Constant):
            found.append((node.arg, value.slice.value, value.lineno))
    return found


# `notification_color=...["highlight"]` reads as correct at the call and is wrong in the
# widget, where the name is all there is to go by.
def test_every_role_colour_is_wired_to_the_token_it_is_named_for() -> None:
    keywords = _role_keywords()
    assert len(keywords) >= 9, "the walk found too few role colours to be proving anything"
    for keyword, token, line in keywords:
        assert keyword == f"{token}_color", f"config.py:{line} passes {token} as {keyword}"


def test_only_the_cells_that_report_an_error_take_the_warning_colour() -> None:
    takes_warning = {
        path.stem for path in (QTILE / "widgets").glob("*.py")
        if "warning_color" in path.read_text(encoding="utf-8")
    }
    assert takes_warning == REPORTS_AN_ERROR


# ---------------------------------------------------------------------------- the cells


def test_updates_are_news_until_they_pile_up(monkeypatch: pytest.MonkeyPatch) -> None:
    widget = WidgetUpdates(r=None, threshold=32, **_roles(WidgetUpdates))
    _streamed(monkeypatch, {"outstanding_updates": 0})
    assert "span" not in widget.poll()
    _streamed(monkeypatch, {"outstanding_updates": 5})
    assert f"color='{NOTIFICATION}'" in widget.poll()
    _streamed(monkeypatch, {"outstanding_updates": 33})
    assert f"color='{HIGHLIGHT}'" in widget.poll()


def test_a_tunnel_being_up_is_news_and_not_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    widget = WidgetVPN(r=None, **_roles(WidgetVPN))
    _streamed(monkeypatch, {"connected": True, "country": "DE"})
    assert f"color='{NOTIFICATION}'" in widget.poll()
    _streamed(monkeypatch, {"connected": False})
    assert "span" not in widget.poll()


def test_a_device_about_to_run_out_is_urgent(monkeypatch: pytest.MonkeyPatch) -> None:
    widget = WidgetBluetooth(r=None, **_roles(WidgetBluetooth))
    widget.font, widget.fontsize = "monospace", 14
    monkeypatch.setattr("shared.glyph_gap.after", lambda *_arguments: " ")
    _streamed(monkeypatch, {"00:11:22:33:44:55": {"capacity": "5"}})
    assert f"color='{HIGHLIGHT}'" in widget.poll()
    _streamed(monkeypatch, {"00:11:22:33:44:55": {"capacity": "80"}})
    assert "span" not in widget.poll()


def test_a_battery_about_to_run_out_is_urgent() -> None:
    widget = WidgetPowerSupply(r=None, **_roles(WidgetPowerSupply))
    assert f"color='{HIGHLIGHT}'" in widget._symbol(10, charging=False)
    assert "span" not in widget._symbol(10, charging=True), "on the charger it is being dealt with"
    assert "span" not in widget._symbol(60, charging=False)


def test_being_on_air_is_urgent(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    widget = WidgetBroadcast(
        r=None, configuration_file_path=str(tmp_path / "config.json"), **_roles(WidgetBroadcast)
    )
    monkeypatch.setattr(widget, "_apply_condition", lambda condition: setattr(widget, "condition", condition))
    _streamed(monkeypatch, {"streaming": True, "obs": True})
    assert f"color='{HIGHLIGHT}'" in widget.poll()
    _streamed(monkeypatch, {"streaming": False, "obs": True})
    assert "span" not in widget.poll()


# The backend's severities are its own words. Its `warning` is a limit three quarters used,
# which is news; its `critical` is one about to be hit, which is urgent; neither has failed.
def test_a_usage_limit_is_news_and_then_urgent_but_never_an_error() -> None:
    widget = WidgetClaudeUsage(r=None, **_roles(WidgetClaudeUsage))
    assert widget._colorize("x", "normal") == "x"
    assert f"color='{NOTIFICATION}'" in widget._colorize("x", "warning")
    assert f"color='{HIGHLIGHT}'" in widget._colorize("x", "critical")


def test_a_broken_sign_in_is_an_error_and_a_missing_reading_is_not() -> None:
    widget = WidgetClaudeUsage(r=None, **_roles(WidgetClaudeUsage))
    widget.measurement = {"available": False, "reason": "token_expired"}
    assert f"color='{WARNING}'" in widget._render()
    widget.measurement = {"available": False, "reason": "no_cache"}
    assert WARNING not in widget._render()


@pytest.mark.parametrize("failure", [1, OSError("no systemctl")])
def test_a_backend_that_is_down_is_an_error(
    monkeypatch: pytest.MonkeyPatch, failure: int | OSError
) -> None:
    def run(*_arguments: object, **_options: object) -> types.SimpleNamespace:
        if isinstance(failure, OSError):
            raise failure
        return types.SimpleNamespace(returncode=failure)

    monkeypatch.setattr(subprocess, "run", run)
    widget = WidgetServiceState(service="backend.service", symbols=symbols.SYMBOLS, **_roles(WidgetServiceState))
    assert f"color='{WARNING}'" in widget.poll()
