"""The theme usage map, and the cross-check that keeps it honest.

The map in `helper/list_palette.py` is recovered by reading the patcher sources rather than
by running them, which is what lets it render on a fresh clone and be policed by
`gendocs.py --check`. The risk that buys is drift: a patcher rewritten into a shape the
walker does not recognise goes quiet rather than wrong, and a report that silently omits a
colour is worse than no report.

So the central test here runs the patchers for real -- into a redirected HOME, with a palette
whose every token is a distinct colour -- and asserts the map and the written file agree in
both directions. Every field the map claims must hold the value it claims, and every themed
field in the file must appear in the map.

Two divergences are deliberate and are asserted as such, because a purely static reading gets
both wrong: web-greeter pins its font size, and plymouth always renders dark.
"""

import ast
import configparser
import json
import pathlib
import pickle
import re
import shutil

import list_palette
import patch_dunst
import patch_gtk
import patch_kitty
import patch_lock
import patch_plymouth
import patch_rofi
import patch_starship
import patch_tmux
import patch_web_greeter
import pytest
import toml
from patch_configurations import PATCHERS
from utils import read_setup

#: One distinct colour per token, so finding a hex in a file identifies which token wrote it.
#: The shipped palettes reuse a hex across tokens (`red_variant` and `failure` are the same
#: colour), which would make every cross-check below ambiguous.
PALETTE = {
    token: f"#{index:02x}00{index:02x}"
    for index, token in enumerate(
        (
            "background", "foreground", "foreground_variant", "neutral", "highlight",
            "notification", "warning", "success", "failure",
            "red", "green", "yellow", "blue", "magenta", "cyan",
            "red_variant", "green_variant", "yellow_variant", "blue_variant",
            "magenta_variant", "cyan_variant",
        ),
        start=1,
    )
}

MONITORS = {"HDMI-0": {"diagonal_dpi": 160.0, "width": 3840, "scaling_factor": 1.6}}


@pytest.fixture
def configuration() -> dict:
    return {
        "name": "default",
        "state": {"theme": "dark"},
        "font": {"family": "SentinelFamily", "size": 33},
        "palette": {"dark": PALETTE, "light": PALETTE},
        "monitors": MONITORS,
        "wallpapers": {
            "dark": "~/.config/qtile/wallpaper-dark.png",
            "light": "~/.config/qtile/wallpaper-light.png",
        },
    }


@pytest.fixture
def home(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    """A HOME the patchers can write into, with the directories they do not create."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for directory in ("kitty", "rofi", "tmux", "dunst", "lock"):
        (tmp_path / ".config" / directory).mkdir(parents=True, exist_ok=True)
    return tmp_path


# --------------------------------------------------------------- reading what was written


def _plain(text: str, separator: str) -> dict[str, str]:
    fields = {}
    for line in text.splitlines():
        if separator in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition(separator)
            fields[key.strip().strip(";").strip()] = value.strip().strip(";").strip()
    return fields


def _ini(text: str) -> dict[str, str]:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(text)
    return {
        f"{section}.{key}": value
        for section in parser.sections()
        for key, value in parser[section].items()
    }


def _flat_toml(text: str) -> dict[str, str]:
    fields = {}

    def walk(node: dict, prefix: str) -> None:
        for key, value in node.items():
            path = f"{prefix}{key}"
            if isinstance(value, dict):
                walk(value, f"{path}.")
            else:
                fields[path] = str(value)

    walk(toml.loads(text), "")
    return fields


def written_fields(configuration: dict, home: pathlib.Path) -> dict[str, dict[str, str]]:
    """Run every patcher whose output can be read back, keyed by the map's target path.

    `patch_gtk` and `patch_web_greeter` are called at the pure stage their own tests use:
    the first shells out to `gsettings` and would rewrite this machine's dconf, the second
    generates into this repository and would leave the login screen showing the fixture.
    """
    patch_kitty.patch_kitty(configuration)
    patch_tmux.patch_tmux(configuration)
    patch_starship.patch_starship(configuration)
    patch_dunst.patch_dunst(configuration)
    patch_rofi.patch_rofi(configuration)
    patch_lock.patch_lock(configuration)

    read = (home / ".config").joinpath
    stylesheet = patch_gtk.gtk_css(configuration, adwaita=True)
    return {
        "_gtk_css_raw": {"": stylesheet},
        "~/.config/kitty/kitty.conf": _plain(read("kitty/kitty.conf").read_text(), " "),
        "~/.config/tmux/tmux.conf": _plain(read("tmux/tmux.conf").read_text(), "="),
        "~/.config/starship.toml": _flat_toml(read("starship.toml").read_text()),
        "~/.config/dunst/dunstrc": _ini(read("dunst/dunstrc").read_text()),
        "~/.config/rofi/theme_config.rasi": _plain(
            read("rofi/theme_config.rasi").read_text(), ":"
        ),
        "~/.config/lock/environment": _plain(read("lock/environment").read_text(), "="),
        "~/.config/gtk-{3,4}.0/gtk.css": _plain(
            stylesheet.replace("@define-color ", ""), " "
        ),
        "~/.config/gtk-{3,4}.0/settings.ini": _plain(
            patch_gtk.render_settings(patch_gtk.gtk_settings(configuration)), "="
        ),
    }


def expected_text(record: list_palette.Usage, configuration: dict) -> str | None:
    """The literal a field must contain for this record to be true."""
    kind, _, name = record.value.partition(".")
    if kind == "palette":
        return configuration["palette"]["dark"][name]
    if kind == "font" and name == "family":
        return configuration["font"]["family"]
    return None  # font.size is scaled, wallpapers are symlinked, state.theme selects


# ------------------------------------------------------------------------- the cross-check


# A patcher rewritten into a shape the ast walker misses would go quiet, not wrong, and the
# report would omit a colour without anything failing. This is what notices.
def test_every_mapped_field_really_holds_the_value_it_claims(
    configuration: dict, home: pathlib.Path
) -> None:
    written = written_fields(configuration, home)
    raw = written["_gtk_css_raw"][""]
    checked = 0
    for record in list_palette.usages():
        if record.target not in written:
            continue
        wanted = expected_text(record, configuration)
        if wanted is None:
            continue
        field = record.key.removeprefix("@define-color ")
        fields = written[record.target]

        if record.how.startswith(list_palette.HOW_ALIASED):
            # The field names a role rather than a colour, which is the point of the
            # indirection: `window_bg_color: @surface` and `surface: <hex>`. Both halves of
            # the chain have to hold, or the report names a colour that never arrives.
            role = record.how.split("`")[1]
            reference = f"@{role}"
            assert reference in (raw if "{" in field else fields.get(field, "")), (
                f"gtk: {field} should reference {reference}"
            )
            assert wanted in fields[role], f"gtk: role {role} should resolve to {wanted}"
        else:
            assert field in fields, (
                f"{record.app}: the map claims a field {field!r} that "
                f"{record.target} has not got"
            )
            assert wanted in fields[field], (
                f"{record.app}: {field} should carry {record.value} ({wanted}), "
                f"but holds {fields[field]!r}"
            )
        checked += 1
    assert checked > 50, "the cross-check silently stopped covering anything"


# The other direction: a colour written into a file that the map does not mention is a value
# the reader would go looking for and not find.
def test_every_themed_field_in_a_written_file_is_in_the_map(
    configuration: dict, home: pathlib.Path
) -> None:
    written = written_fields(configuration, home)
    hexes = {value.lower(): token for token, value in PALETTE.items()}
    records = list_palette.usages()
    for target, fields in written.items():
        if target.startswith("_"):
            continue
        mapped = {r.key.removeprefix("@define-color ") for r in records if r.target == target}
        for field, value in fields.items():
            for found in list_palette.HEX_RE.findall(value):
                if found.lower() in hexes:
                    assert field in mapped, (
                        f"{target} writes {hexes[found.lower()]} into {field!r}, "
                        "which the usage map does not mention"
                    )


# --------------------------------------------------------------- the two known divergences


# A static reading of `theme_variables` reports the theme's font size reaching the login
# screen. It does not: theme.json#font_overrides is merged over it and pins a size.
def test_the_login_screen_font_size_is_reported_as_pinned(configuration: dict) -> None:
    pinned = [
        record
        for record in list_palette.usages()
        if record.app == "web-greeter" and record.value == "font.size"
    ]
    assert pinned, "web-greeter's font size is not in the map at all"
    assert all(record.how.startswith(list_palette.HOW_PINNED) for record in pinned)

    manifest = json.loads(
        (
            list_palette.REPO_ROOT
            / "configuration/web-greeter/themes/standard/theme.json"
        ).read_text()
    )
    variables = patch_web_greeter.theme_variables(configuration, manifest, "wallpaper.png")
    assert variables["--font-size"] != f"{configuration['font']['size']}px"


# `PALETTE_VARIANT` is passed to render_theme unconditionally, so state.theme never reaches
# the boot splash. Reporting it as following the active theme would be a lie about a screen
# nobody sees often enough to notice.
def test_plymouth_is_reported_as_always_dark(
    configuration: dict, tmp_path: pathlib.Path
) -> None:
    records = [r for r in list_palette.usages() if r.app == "plymouth"]
    assert records
    assert all("always dark" in record.how for record in records)

    source = list_palette.REPO_ROOT / "configuration/plymouth/theme"
    staged = tmp_path / "staged"
    # `background-tile.png` in that directory is a tracked symlink to a wallpaper the
    # installer materialises, and wallpapers are gitignored -- so in a fresh clone it dangles
    # and a plain copytree raises. The INI is all render_configuration reads.
    shutil.copytree(source, staged, ignore_dangling_symlinks=True)
    light = dict(configuration, state={"theme": "light"})
    light["palette"] = {"dark": PALETTE, "light": dict.fromkeys(PALETTE, "#ffffff")}
    patch_plymouth.render_configuration(light, str(staged), patch_plymouth.PALETTE_VARIANT, "d")

    parser = configparser.ConfigParser(interpolation=None)
    parser.read(str(staged / "d.plymouth"))
    written = parser["two-step"]["BackgroundStartColor"]
    assert written == PALETTE["background"].replace("#", "0x"), (
        "the splash followed state.theme; the map says it cannot"
    )


# --------------------------------------------------------------------------- the map itself


# TARGETS is the one hand-written table left. A path that names a file its patcher does not
# write is the failure mode the curated PLYMOUTH_ROLES constant had before this replaced it.
def test_every_declared_target_appears_in_the_source_it_is_claimed_for() -> None:
    for (stem, function), target in list_palette.TARGETS.items():
        source = (list_palette.REPO_ROOT / "helper" / f"{stem}.py").read_text()
        assert f"def {function}(" in source, f"{stem}.py has no {function}()"
        literals = [part for part in re.findall(r"[A-Za-z0-9_.]{4,}", target) if "." in part]
        assert any(part in source for part in literals), (
            f"{stem}.py never mentions any part of {target} ({literals})"
        )


#: Registered patchers the usage map cannot contain, and why. The map is recovered by reading
#: which palette *token* a patcher names, so a patcher that names none cannot appear in it.
DECLARES_NO_TOKEN = {
    # Scales the X server's DPI to the monitors and reads no theme value at all.
    "xorg",
    # Resolves its colours perceptually instead of naming tokens: every qutebrowser default is
    # replaced by whichever token is nearest it. What it maps to is in docs/color-distance.md
    # and the vscode section of docs/palette-reference.md, both of which compute the match
    # rather than reading it out of the source.
    "qutebrowser",
}


def test_every_patcher_that_reads_the_theme_is_in_the_map() -> None:
    mapped = {record.app for record in list_palette.usages()}
    expected = {name for name, _ in PATCHERS} - DECLARES_NO_TOKEN
    assert expected <= mapped, f"missing from the usage map: {sorted(expected - mapped)}"


def test_the_patchers_that_declare_no_token_really_declare_none() -> None:
    """Otherwise the exclusion above becomes a way to hide a patcher that broke."""
    mapped = {record.app for record in list_palette.usages()}
    assert not (DECLARES_NO_TOKEN & mapped), (
        f"{sorted(DECLARES_NO_TOKEN & mapped)} names tokens after all; drop it from the set"
    )


def test_every_palette_token_reaches_at_least_one_consumer() -> None:
    used = {r.value.removeprefix("palette.") for r in list_palette.usages()
            if r.value.startswith("palette.")}
    assert set(PALETTE) == used, (
        f"tokens no consumer reads: {sorted(set(PALETTE) - used)}; "
        f"consumed but not in the vocabulary: {sorted(used - set(PALETTE))}"
    )


# What justifies registering this block with gendocs at all: if any of it varied per machine,
# the pre-commit hook would refuse a commit on every install but the one that generated it --
# which is exactly what switching themes used to do, back when the hex values were read from
# `~/.config/config.json`.
def test_nothing_in_the_block_reads_the_active_install(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = list_palette.generate_markdown()
    monkeypatch.setenv("HOME", str(tmp_path))
    assert list_palette.generate_markdown() == before, (
        "the block changed when ~/ did, so it describes this machine rather than the repository"
    )


def test_the_palette_shown_is_the_configured_bundles() -> None:
    """Named rather than inferred: the document says which bundle it is describing."""
    configured = read_setup()["desktop"]["theme"]
    with (list_palette.REPO_ROOT / "assets" / configured / "palette.pkl").open("rb") as handle:
        shipped = pickle.load(handle)
    config = list_palette._load_active_config()
    assert config["palette"] == shipped


def test_the_markdown_is_the_same_on_a_second_run() -> None:
    assert list_palette.generate_markdown() == list_palette.generate_markdown()


# ----------------------------------------------------------------------- the ast shapes


@pytest.mark.parametrize(
    ("source", "value", "key"),
    [
        # The two spellings that reach the palette, and the scaling the font goes through.
        ('def f(configuration):\n d = {"a": configuration["palette"][t]["highlight"]}', "palette.highlight", "a"),
        ('def f(configuration):\n p = configuration["palette"][t]\n d = {"a": p["neutral"]}', "palette.neutral", "a"),
        ('def f(configuration):\n x["g"]["h"] = configuration["palette"][t]["red"]', "palette.red", "g.h"),
        ('def f(configuration):\n d = {"a": round(configuration["font"]["size"] * 0.5)}', "font.size", "a"),
    ],
)
def test_each_recognised_shape_resolves(source: str, value: str, key: str) -> None:
    tree = ast.parse(source)
    parents = list_palette._parents(tree)
    function = tree.body[0]
    aliases = list_palette._aliases(function)
    found = []
    for node in ast.walk(function):
        resolved = list_palette._theme_value(node, aliases)
        if resolved:
            holder, how = list_palette._climb(node, parents, {})
            field = list_palette._field(
                holder, list_palette._child_of(node, holder, parents), aliases
            )
            found.append((resolved, field, how))
    assert (value, key) in [(v, f) for v, f, _ in found], found
