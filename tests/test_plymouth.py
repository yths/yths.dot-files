"""The boot splash: rendered dark whatever the desktop does, and named for where it installs.

Two things here are easy to get wrong and invisible when they are. The splash is drawn before
anyone logs in, so it has no user whose light/dark preference could apply -- it is always
rendered from the dark palette, and `state.theme` describes a session that does not exist yet.

And `ImageDir` is an absolute path into the system theme directory, so it has to name the
directory `install_theme` is about to create. It did not once: after a bundle was renamed, the
theme installed under the new name while its INI still pointed at the old one, which plymouth
answers by drawing no images at all.

The splash installs under the active theme's name, and installing also names it in
`/etc/plymouth/plymouthd.conf`. The two have to move together: once the installed name changed
while nothing updated plymouthd.conf, and the splash stayed thirteen months old without a word.
"""

import configparser
import ctypes
import json
import os
import pathlib
import re
import shutil
import subprocess
from collections.abc import Callable, Iterator

import patch_plymouth
import PIL.Image
import pytest
import symbols
import utils

PALETTE = {"background": "#322f2f", "foreground": "#d5d1d1", "neutral": "#afabab",
           "highlight": "#4d91c7"}
LIGHT = {"background": "#fffbfb", "foreground": "#4f4c4c", "neutral": "#8d8989",
         "highlight": "#4d91c7"}

class _ScriptReturn(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("object", ctypes.c_void_p)]


@pytest.fixture
def plymouth_script(
    configuration: dict, staged: pathlib.Path,
) -> Iterator[Callable[[str], bool]]:
    """Run the actual script interpreter and image/sprite libraries without a daemon."""
    plugin = pathlib.Path("/usr/lib/plymouth/script.so")
    if not plugin.exists():
        pytest.skip("Plymouth's script plugin is not installed")
    library = ctypes.CDLL(str(plugin))
    pointer = ctypes.c_void_p
    signatures = {
        "script_state_new": ([pointer], pointer),
        "script_state_destroy": ([pointer], None),
        "script_parse_string": ([ctypes.c_char_p, ctypes.c_char_p], pointer),
        "script_parse_op_free": ([pointer], None),
        "script_execute": ([pointer, pointer], _ScriptReturn),
        "script_obj_as_bool": ([pointer], ctypes.c_bool),
        "script_obj_unref": ([pointer], None),
        "script_lib_image_setup": ([pointer, ctypes.c_char_p], pointer),
        "script_lib_image_destroy": ([pointer], None),
        "script_lib_math_setup": ([pointer], pointer),
        "script_lib_math_destroy": ([pointer], None),
        "script_lib_sprite_setup": ([pointer, pointer, pointer, ctypes.c_char_p, ctypes.c_uint32,
                                     ctypes.c_uint32], pointer),
        "script_lib_sprite_destroy": ([pointer], None),
        "ply_list_new": ([], pointer),
        "ply_list_free": ([pointer], None),
        "ply_buffer_new": ([], pointer),
        "ply_buffer_free": ([pointer], None),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(library, name)
        function.argtypes = arguments
        function.restype = result
    configuration["symbols"] = {"plymouth.bullet": "o"}
    patch_plymouth.render_theme(configuration, str(staged), "dark", "test")
    state = library.script_state_new(None)
    displays = library.ply_list_new()
    buffer = library.ply_buffer_new()
    images = library.script_lib_image_setup(state, os.fsencode(staged))
    math = library.script_lib_math_setup(state)
    sprites = library.script_lib_sprite_setup(state, displays, buffer, None, 0, 0)
    operations = []

    def run(source: str) -> bool:
        operation = library.script_parse_string(source.encode(), b"test-plymouth")
        assert operation, "Plymouth could not parse the theme"
        operations.append(operation)
        result = library.script_execute(state, operation)
        assert result.type != 2, "Plymouth could not execute the theme"
        truth = bool(result.object and library.script_obj_as_bool(result.object))
        library.script_obj_unref(result.object)
        return truth

    run("""
        fun width(index) { if (index == 0) return 1366; return NULL; }
        fun height(index) { if (index == 0) return 768; return NULL; }
        fun origin(index) { return 0; }
        fun ignore(a, b) { }
        fun mode() { return "boot"; }
        fun capslock() { return 0; }
        fun keyboard() { return test_layout; }
        test_layout = NULL;
        Window.GetWidth = width; Window.GetHeight = height;
        Window.GetX = origin; Window.GetY = origin;
        Window.SetX = ignore; Window.SetY = ignore;
        Plymouth.GetMode = mode; Plymouth.GetCapslockState = capslock;
        Plymouth.GetKeyboardLayout = keyboard;
        Plymouth.SetRefreshFunction = ignore; Plymouth.SetDisplayHotplugFunction = ignore;
        Plymouth.SetDisplayNormalFunction = ignore; Plymouth.SetDisplayPasswordFunction = ignore;
        Plymouth.SetDisplayQuestionFunction = ignore; Plymouth.SetDisplayPromptFunction = ignore;
        Plymouth.SetDisplayMessageFunction = ignore; Plymouth.SetHideMessageFunction = ignore;
    """)
    run((staged / "theme.script").read_text())
    try:
        yield run
    finally:
        library.script_state_destroy(state)
        library.script_lib_sprite_destroy(sprites)
        library.script_lib_image_destroy(images)
        library.script_lib_math_destroy(math)
        library.ply_list_free(displays)
        library.ply_buffer_free(buffer)
        for operation in operations:
            library.script_parse_op_free(operation)


def test_password_uses_the_rendered_theme_bullet_and_clears_deleted_input(
    plymouth_script: Callable[[str], bool],
) -> None:
    assert plymouth_script("""
        display_password("Unlock:", 4);
        return views[0].entry.GetImage().GetWidth() == bullet_image.GetWidth() * 4 &&
               views[0].entry.GetImage().GetHeight() == bullet_image.GetHeight() &&
               views[0].entry.GetOpacity() == 1 && entry_text == "";
    """)
    assert plymouth_script("""
        display_password("Unlock:", 1);
        return views[0].entry.GetImage().GetWidth() == bullet_image.GetWidth();
    """)
    assert plymouth_script("""
        display_password("Unlock:", 1000);
        return views[0].entry.GetImage().GetWidth() <=
               Window.GetWidth(0) * 0.95 - views[0].entry.GetX();
    """)
    assert plymouth_script("""
        display_password("Unlock:", 0);
        return views[0].entry.GetOpacity() == 0;
    """)
    assert plymouth_script("""
        display_question("Recovery:", "answer");
        return views[0].entry.GetOpacity() == 1 && entry_text == "answer";
    """)


@pytest.mark.parametrize("bullet_height", [10, 11, 40])
def test_password_bullets_are_vertically_centered_with_the_lock(
    plymouth_script: Callable[[str], bool], bullet_height: int,
) -> None:
    assert plymouth_script(f"""
        bullet_image = bullet_image.Scale(bullet_image.GetWidth(), {bullet_height});
        display_password("Unlock:", 4);
        local.entry_center = views[0].entry.GetY() + views[0].entry.GetImage().GetHeight() / 2;
        local.lock_center = views[0].lock.GetY() + lock_image.GetHeight() / 2;
        return entry_center - lock_center >= -0.5 && entry_center - lock_center <= 0.5;
    """)


def test_keyboard_layout_is_hidden_when_unknown_and_updates_when_available(
    plymouth_script: Callable[[str], bool],
) -> None:
    assert plymouth_script("""
        display_password("Unlock:", 1);
        return views[0].keyboard.GetOpacity() == 0;
    """)
    assert plymouth_script("""
        test_layout = "de";
        refresh();
        return keyboard_layout == "de" && views[0].keyboard.GetOpacity() == 1 &&
               views[0].keyboard.GetImage().GetWidth() == text_image("de").GetWidth();
    """)
    assert plymouth_script("""
        test_layout = "";
        refresh();
        return views[0].keyboard.GetOpacity() == 0;
    """)
    assert plymouth_script("""
        test_layout = NULL;
        refresh();
        return views[0].keyboard.GetOpacity() == 0;
    """)
    assert plymouth_script("""
        test_layout = "us";
        refresh();
        display_normal();
        return views[0].keyboard.GetOpacity() == 0 && password_bullets == 0;
    """)


@pytest.fixture
def configuration() -> dict:
    return {
        "name": "default",
        "state": {"theme": "light"},          # deliberately light: the splash must ignore it
        "palette": {"dark": PALETTE, "light": LIGHT},
        "font": {"family": "Iosevka NF", "size": 16},
    }


@pytest.fixture
def staged(tmp_path: pathlib.Path) -> pathlib.Path:
    """A staging directory holding the shipped configuration and layout template."""
    source = pathlib.Path(patch_plymouth.THEME_SOURCE)
    for name in ("theme.plymouth", "theme.script.in"):
        shutil.copyfile(source / name, tmp_path / name)
    return tmp_path


def _ini(path: pathlib.Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    # Whatever the render named it: the INI is renamed to <name>.plymouth.
    (ini,) = path.glob("*.plymouth")
    parser.read(ini)
    return parser


def test_the_splash_is_rendered_dark(configuration: dict, staged: pathlib.Path) -> None:
    """`state.theme` is "light" in the fixture; the splash must not follow it."""
    patch_plymouth.render_configuration(
        configuration, str(staged), patch_plymouth.PALETTE_VARIANT, "default"
    )
    assert _ini(staged)["script"]["BackgroundStartColor"] == "0x322f2f"


def test_the_dark_variant_is_what_the_pipeline_asks_for() -> None:
    assert patch_plymouth.PALETTE_VARIANT == "dark"


def test_colours_are_written_the_way_plymouth_reads_them(
    configuration: dict, staged: pathlib.Path
) -> None:
    """0xrrggbb, not #rrggbb; plymouth silently ignores what it cannot parse."""
    patch_plymouth.render_configuration(configuration, str(staged), "dark", "default")
    settings = _ini(staged)["script"]
    for key in ("BackgroundStartColor", "BackgroundEndColor",
                "ConsoleLogTextColor", "ConsoleLogBackgroundColor"):
        assert settings[key].startswith("0x"), key
        assert "#" not in settings[key], key


def test_image_dir_names_where_the_theme_installs(
    configuration: dict, staged: pathlib.Path
) -> None:
    """The regression: a renamed preset left this pointing at the old directory."""
    patch_plymouth.render_configuration(configuration, str(staged), "dark", "somepreset")
    expected = os.path.join(patch_plymouth.SYSTEM_THEME_ROOT, "somepreset")
    assert _ini(staged)["script"]["ImageDir"] == expected
    assert _ini(staged)["script"]["ScriptFile"] == os.path.join(expected, "theme.script")


def test_the_theme_names_itself_after_what_it_installs_as(
    configuration: dict, staged: pathlib.Path
) -> None:
    """`ImageDir` is an absolute path into the system theme directory, so the name in the INI and
    the directory it installs to have to be the same string."""
    patch_plymouth.render_configuration(configuration, str(staged), "dark", "somename")
    assert _ini(staged)["Plymouth Theme"]["Name"] == "somename"
    assert _ini(staged)["script"]["ImageDir"].endswith("/somename")


# The splash is one theme for every bundle. It was found by looking for a directory named after
# the active preset, so a bundle exported under any other name silently got none -- and "a preset
# need not ship one" made that indistinguishable from a deliberate omission.
def test_the_splash_does_not_depend_on_which_bundle_is_installed() -> None:
    for name in ("default", "autumn-dawn", "something-nobody-has-exported-yet", None):
        assert patch_plymouth.theme_source({"name": name}) == patch_plymouth.THEME_SOURCE


# plymouth finds a theme's INI as themes/<name>/<name>.plymouth.
def test_the_ini_is_named_for_the_theme(configuration: dict, staged: pathlib.Path) -> None:
    patch_plymouth.render_configuration(configuration, str(staged), "dark", "autumn")
    assert [path.name for path in staged.glob("*.plymouth")] == ["autumn.plymouth"]


@pytest.mark.parametrize(
    ("bundle_name", "expected"),
    [("default", "dot-files-default"), ("Default", "dot-files-default"), ("Autumn Theme", "autumn-theme")],
)
def test_plymouth_theme_names_avoid_the_reset_command(bundle_name: str, expected: str) -> None:
    assert patch_plymouth.plymouth_theme_name({"name": bundle_name}) == expected


def test_system_install_renders_and_selects_the_safe_default_name(
    configuration: dict, staged: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(patch_plymouth, "stage_theme", lambda _source: str(staged))
    monkeypatch.setattr(patch_plymouth, "render_assets", lambda *_args: None)

    def install(path: str, name: str, *, prompt: bool, rebuild: bool) -> bool:
        assert name == "dot-files-default"
        assert (pathlib.Path(path) / f"{name}.plymouth").is_file()
        assert _ini(pathlib.Path(path))["script"]["ImageDir"].endswith(f"/{name}")
        assert prompt and rebuild
        return True

    monkeypatch.setattr(patch_plymouth, "install_theme", install)
    assert patch_plymouth.install_system(configuration, prompt=True)


def test_installing_makes_it_the_default_and_removes_earlier_ones(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """plymouthd.conf has to name what was installed, in the same step.

    Once it did not: the installed name changed while plymouthd.conf kept naming the old one,
    and the splash stayed thirteen months old.
    """
    root = tmp_path / "themes"
    for name, ours in (("earlier", True), ("from-a-package", False)):
        (root / name).mkdir(parents=True)
        if ours:
            (root / name / utils.INSTALL_MARKER).write_text("")
    calls = []

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        calls.append(argv)
        if argv[0] == "rm":
            shutil.rmtree(argv[-1])
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(patch_plymouth, "SYSTEM_THEME_ROOT", str(root))
    monkeypatch.setattr(patch_plymouth, "root_prefix", lambda **_kwargs: [])
    monkeypatch.setattr(patch_plymouth.subprocess, "run", run)

    assert patch_plymouth.install_theme(str(tmp_path), "autumn")
    assert ["plymouth-set-default-theme", "autumn"] in calls
    assert sorted(path.name for path in root.iterdir()) == ["from-a-package"], (
        "the earlier splash this repository installed is gone; the package's is not"
    )


def test_the_fonts_scale_from_the_configured_size(
    configuration: dict, staged: pathlib.Path
) -> None:
    patch_plymouth.render_configuration(configuration, str(staged), "dark", "default")
    settings = _ini(staged)["script"]
    assert settings["Font"] == "Iosevka NF 20"            # 16 * 1.25
    assert settings["MonospaceFont"] == "Iosevka NF 14"   # 16 * 0.85


def test_a_missing_ini_is_named_rather_than_guessed(
    configuration: dict, tmp_path: pathlib.Path
) -> None:
    """The INI is found by glob, because the staging directory's name is not the theme's."""
    with pytest.raises(FileNotFoundError, match=re.escape("no .plymouth file")):
        patch_plymouth.render_configuration(configuration, str(tmp_path), "dark", "default")


def test_a_bundle_without_its_own_splash_still_gets_one(configuration: dict) -> None:
    """The opposite of what this asserted before, and the reason it changed.

    A splash found by preset name meant a bundle exported under any other name got none, silently
    -- "a preset need not ship one" made a missing directory indistinguishable from a choice.
    There is one splash now, and every bundle gets it with its own colours.
    """
    configuration["name"] = "a-bundle-that-ships-none"
    assert patch_plymouth.theme_source(configuration) is not None


def test_the_shipped_preset_has_a_splash(configuration: dict) -> None:
    assert patch_plymouth.theme_source(configuration) is not None


def test_staging_refuses_a_dangling_wallpaper_link(tmp_path: pathlib.Path) -> None:
    """background-tile.png links to the active wallpaper, which install.py creates. Copying a
    dangling link produces a theme that boots to nothing, so it is refused with the fix."""
    source = tmp_path / "theme"
    source.mkdir()
    (source / "theme.plymouth").write_text("[script]\n")
    os.symlink(tmp_path / "no-such-wallpaper.png", source / "background-tile.png")
    with pytest.raises(FileNotFoundError, match=re.escape("install.py")):
        patch_plymouth.stage_theme(str(source))


def test_staging_copies_rather_than_rendering_in_place(tmp_path: pathlib.Path) -> None:
    """Rendering in place would rewrite tracked files on every run."""
    source = tmp_path / "theme"
    source.mkdir()
    (source / "theme.plymouth").write_text("[script]\nFont=original\n")
    staged = patch_plymouth.stage_theme(str(source))
    try:
        assert staged != str(source)
        (pathlib.Path(staged) / "theme.plymouth").write_text("[script]\nFont=changed\n")
        assert "original" in (source / "theme.plymouth").read_text()
    finally:
        shutil.rmtree(staged, ignore_errors=True)


# --------------------------------------------------------------- the themeable messages
#
# Until the symbol vocabulary existed these were the one part of the splash a theme could not
# reach: the patcher rewrote the fonts and colours around them and left the words in the
# checked-in INI, so every bundle booted to the same seven titles.


def test_every_mode_gets_its_title_and_subtitle_from_the_vocabulary(
    configuration: dict, staged: pathlib.Path
) -> None:
    patch_plymouth.render_configuration(
        configuration, str(staged), patch_plymouth.PALETTE_VARIANT, "default"
    )
    parser = _ini(staged)
    _, strings = symbols.resolve(configuration)
    for section, prefix in symbols.PLYMOUTH_SECTIONS.items():
        assert parser[section]["Title"] == strings[f"plymouth.{prefix}.title"]
        assert parser[section]["SubTitle"] == strings[f"plymouth.{prefix}.subtitle"]


def test_a_theme_can_change_one_message_without_touching_the_rest(
    configuration: dict, staged: pathlib.Path
) -> None:
    configuration["strings"] = {"plymouth.reboot.title": "See you shortly."}
    patch_plymouth.render_configuration(
        configuration, str(staged), patch_plymouth.PALETTE_VARIANT, "default"
    )
    parser = _ini(staged)
    assert parser["reboot"]["Title"] == "See you shortly."
    assert parser["boot-up"]["Title"] == symbols.STRINGS["plymouth.boot.title"]


# optionxform is off, so `Subtitle` and `SubTitle` are two keys rather than one. Writing the
# wrong capital leaves the original in place and adds a second the splash never reads.
def test_the_subtitle_spelling_is_plymouths(
    configuration: dict, staged: pathlib.Path
) -> None:
    patch_plymouth.render_configuration(
        configuration, str(staged), patch_plymouth.PALETTE_VARIANT, "default"
    )
    for section in symbols.PLYMOUTH_SECTIONS:
        keys = [key for key in _ini(staged)[section] if key.lower() == "subtitle"]
        assert keys == ["SubTitle"], f"[{section}] ended up with {keys}"


def test_a_section_the_ini_does_not_carry_is_not_invented(
    configuration: dict, staged: pathlib.Path
) -> None:
    """The section list is plymouth's. Adding one declares a mode with no animation."""
    before = set(_ini(staged).sections())
    patch_plymouth.render_configuration(
        configuration, str(staged), patch_plymouth.PALETTE_VARIANT, "default"
    )
    assert set(_ini(staged).sections()) == before


def test_script_receives_the_rendered_font_palette_and_all_modes(
    configuration: dict, staged: pathlib.Path,
) -> None:
    patch_plymouth.render_configuration(configuration, str(staged), "dark", "default")
    assignments = {}
    for line in (staged / "theme.script").read_text().splitlines():
        if not line.startswith("theme."):
            break
        key, value = line.removesuffix(";").split(" = ", 1)
        assignments[key] = json.loads(value)
    assert _ini(staged)["Plymouth Theme"]["ModuleName"] == "script"
    assert assignments["theme.font"] == "Iosevka NF 20"
    assert assignments["theme.background_red"] == pytest.approx(0x32 / 255)
    _, strings = symbols.resolve(configuration)
    for section, prefix in symbols.PLYMOUTH_SECTIONS.items():
        mode = "boot" if section == "boot-up" else section
        assert assignments[f'theme.titles["{mode}"]'] == strings[f"plymouth.{prefix}.title"]
        assert assignments[f'theme.subtitles["{mode}"]'] == strings[f"plymouth.{prefix}.subtitle"]


def test_custom_messages_are_script_strings_not_executable_source(
    configuration: dict, staged: pathlib.Path,
) -> None:
    title = 'Restarting "now";\n\\ wait'
    configuration["strings"] = {"plymouth.reboot.title": title}
    patch_plymouth.render_configuration(configuration, str(staged), "dark", "default")
    script = (staged / "theme.script").read_text()
    assignment = next(line for line in script.splitlines() if line.startswith('theme.titles["reboot"]'))
    assert json.loads(assignment.split(" = ", 1)[1].removesuffix(";")) == title


def test_throbber_alignment_uses_visible_pixels_not_transparent_padding(
    configuration: dict, staged: pathlib.Path,
) -> None:
    patch_plymouth.render_assets(configuration, str(staged), "dark")
    for filename in ("throbber-01.png", "throbber-02.png"):
        with PIL.Image.open(staged / filename) as image:
            assert image.getbbox() == (0, 0, *image.size)


# The splash is the one surface where a missing glyph is baked into a PNG rather than merely
# displayed, so it survives until the next theme switch.
def test_the_rendered_glyphs_come_from_the_vocabulary() -> None:
    declared = {key for *_rest, key in patch_plymouth.GLYPH_ASSETS}
    assert declared <= set(symbols.SYMBOLS), f"undeclared: {declared - set(symbols.SYMBOLS)}"
    for key in declared:
        assert symbols.SYMBOLS[key].isascii(), f"{key} falls back to a glyph, not ascii"


def test_the_missing_hook_is_detected_but_never_written(tmp_path: pathlib.Path) -> None:
    # Whether the splash draws is decided in a file that decides whether the machine boots,
    # so the installer only reports. The HOOKS= line is parsed as a word list: a hook named
    # elsewhere in the file, in a comment, is not the hook.
    config = tmp_path / "mkinitcpio.conf"
    config.write_text("# plymouth goes here\nHOOKS=(base systemd sd-encrypt filesystems)\n")
    assert patch_plymouth.hook_is_configured(str(config)) is False
    config.write_text("HOOKS=(base systemd plymouth sd-encrypt filesystems)\n")
    assert patch_plymouth.hook_is_configured(str(config)) is True
    assert patch_plymouth.hook_is_configured(str(tmp_path / "absent")) is None
