"""Summarise what a theme sets and where every one of those values is used.

A theme sets three kinds of value -- the palette's tokens, the font, and the wallpapers --
and they reach a dozen applications through the ``helper/patch_<app>.py`` patchers. There is
no templating anywhere in that path: each patcher reads the value and writes the target
application's own format, so the map from "theme value" to "the field it lands in" exists
only as Python spread across a dozen modules. This module recovers it and renders it two
ways round.

Four views, emitted as markdown:

1. **Palette** -- the active ``token -> hex`` table (light/dark) read from
   ``~/.config/config.json``.
2. **Theme value -> usage** -- for each value a theme sets, every field that carries it.
   Answers "if I change ``highlight``, what moves?"
3. **Configuration file -> theme values** -- for each generated file, what it carries and
   where each field came from. Answers "where did this value in my dunstrc come from?"
4. **Drift report** -- tools that hardcode hex *outside* the palette; each colour is
   reverse-mapped to its nearest palette token through ``helper/color_match.py``, the same
   matcher the VSCode and qutebrowser patchers resolve their colours with.

Views 2 and 3 are two renderings of one list of :class:`Usage` records, recovered by reading
the patcher sources with ``ast`` rather than by running them. Static extraction is what lets
this run on a fresh clone with no install, and lets ``gendocs.py --check`` police it in the
pre-commit hook -- but it reports what the source *says*, so two divergences are recorded
explicitly rather than inferred, and ``tests/test_list_palette.py`` cross-checks the whole
map against what the patchers actually write:

- web-greeter's font size is **pinned** by ``theme.json#font_overrides``, not themed.
- plymouth always renders the **dark** variant, whatever ``state.theme`` holds.

``generate_markdown`` returns the body that ``gendocs.py`` injects into
``docs/palette-reference.md``; running the module prints the same body, and ``--value`` /
``--app`` / ``--file`` narrow it to one lookup. The usage map is repo-derived and identical
on every machine; the hex values and ΔE distances reflect the active install.
"""

import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(os.path.expanduser("~/.config/config.json"))

HEX_RE = re.compile(r"#[0-9a-fA-F]{6}")

try:  # the perceptual sections reuse the shared matcher in helper/color_match.py
    import color_match
    import patch_vsc

    _HAVE_COLOUR = True
except ImportError:
    _HAVE_COLOUR = False


def _escape(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def _load_active_config() -> dict | None:
    try:
        return json.loads(CONFIG_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return None


# ------------------------------------------------------------------ palette table


def _palette_section(config: dict) -> str:
    lines = ["### Palette (`~/.config/config.json`)", ""]
    if not config or "palette" not in config:
        lines.append(
            "_No active `~/.config/config.json` found — run the installer to materialise "
            "a palette. The usage map below is parsed from the repo and is unaffected._"
        )
        return "\n".join(lines)

    light = config["palette"].get("light", {})
    dark = config["palette"].get("dark", {})
    tokens = list(dict.fromkeys(list(light) + list(dark)))
    lines.append("| Token | Light | Dark |")
    lines.append("| --- | --- | --- |")
    for token in tokens:
        lines.append(
            f"| `{_escape(token)}` | `{_escape(light.get(token, '—'))}` "
            f"| `{_escape(dark.get(token, '—'))}` |"
        )
    lines.append("")
    lines.append("_Hex values reflect the active theme bundle and differ per install._")
    return "\n".join(lines)


# ------------------------------------------------------------------- usage records


class Usage(NamedTuple):
    """One theme value landing in one field of one file.

    ``value`` names what the theme set (``palette.highlight``, ``font.size``,
    ``wallpapers.dark``); ``key`` names the field it lands in, in the target file's own
    vocabulary; ``how`` says what happened to it on the way -- see ``HOW_*`` below.
    """

    value: str
    app: str
    target: str
    key: str
    how: str
    source: str


#: ``how`` is a closed vocabulary so the column can be scanned rather than read.
HOW_DIRECT = "direct"
HOW_EMBEDDED = "embedded"
HOW_ALIASED = "via role"
HOW_PINNED = "pinned"
HOW_NEAREST = "nearest match"
HOW_RENDERED = "rendered"

#: Where each extracted function's output lands. Keyed by ``(module stem, function)`` rather
#: than by app because two of them write more than one file. ``tests/test_list_palette.py``
#: asserts every path here appears in the source it is claimed for, so this cannot drift
#: into fiction the way a hand-written table otherwise would.
TARGETS: dict[tuple[str, str], str] = {
    ("patch_kitty", "kitty_configuration"): "~/.config/kitty/kitty.conf",
    ("patch_lock", "lock_environment"): "~/.config/lock/environment",
    ("patch_tmux", "patch_tmux"): "~/.config/tmux/tmux.conf",
    ("patch_starship", "patch_starship"): "~/.config/starship.toml",
    ("patch_dunst", "patch_dunst"): "~/.config/dunst/dunstrc",
    ("patch_rofi", "patch_rofi"): "~/.config/rofi/theme_config.rasi",
    ("patch_gtk", "gtk_roles"): "~/.config/gtk-{3,4}.0/gtk.css",
    ("patch_gtk", "gtk_css"): "~/.config/gtk-{3,4}.0/gtk.css",
    ("patch_gtk", "gtk_settings"): "~/.config/gtk-{3,4}.0/settings.ini",
    ("patch_plymouth", "render_configuration"): "/usr/share/plymouth/themes/<preset>.plymouth",
    ("patch_plymouth", "render_assets"): "/usr/share/plymouth/themes/<preset>/*.png",
}

#: The app each patcher module configures, for the ``app`` column.
APPS: dict[str, str] = {
    "patch_kitty": "kitty",
    "patch_lock": "lock",
    "patch_tmux": "tmux",
    "patch_starship": "starship",
    "patch_dunst": "dunst",
    "patch_rofi": "rofi",
    "patch_gtk": "gtk",
    "patch_plymouth": "plymouth",
}


# ---------------------------------------------------------------- the ast extractor


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    """Child -> parent for the whole tree; ``ast`` does not record it."""
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _string_slice(node: ast.AST) -> str | None:
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
        value = node.slice.value
        return value if isinstance(value, str) else None
    return None


#: Stands for a subscript that is not a literal -- the ``[theme]`` in
#: ``configuration["palette"][theme]["highlight"]``, or the loop variable in
#: ``palette[token]``. Kept in the path rather than ending the walk, because the interesting
#: key is usually the one *after* it.
ANY_KEY = "*"


def _subscript_path(node: ast.AST) -> list[str]:
    """``a["x"][k]["y"]`` -> ``["x", ANY_KEY, "y"]``, innermost first."""
    path = []
    current = node
    while isinstance(current, ast.Subscript):
        path.insert(0, _string_slice(current) or ANY_KEY)
        current = current.value
    return path


def _base_name(node: ast.AST) -> str | None:
    current = node
    while isinstance(current, ast.Subscript):
        current = current.value
    return current.id if isinstance(current, ast.Name) else None


def _theme_value(node: ast.AST, aliases: dict[str, list[str]]) -> str | None:
    """The theme value ``node`` reads, as ``palette.<token>`` / ``font.size`` / ..., or None.

    Two spellings reach the same place and both are in use: the full
    ``configuration["palette"][theme]["<token>"]`` (53 sites) and the local
    ``palette["<token>"]`` (14 sites) left behind when a patcher hoists the lookup.
    """
    if not isinstance(node, ast.Subscript):
        return None
    path = _subscript_path(node)
    base = _base_name(node)
    if base is None or not path:
        return None
    if base == "configuration":
        return _from_configuration(path)
    prefix = aliases.get(base)
    if prefix is not None:
        return _from_configuration([*prefix, *path])
    return None


def _from_configuration(path: list[str]) -> str | None:
    """``["palette", ANY_KEY, "highlight"]`` -> ``palette.highlight``.

    A value whose own key is not a literal -- ``palette[token]`` inside a loop -- resolves to
    nothing here on purpose. Those are driven by a module-level table, and an expander below
    reads the table itself rather than guessing from the loop.
    """
    named = {"palette": 2, "font": 1, "wallpapers": 1}
    depth = named.get(path[0])
    if depth is None:
        return "state.theme" if path[:2] == ["state", "theme"] else None
    if len(path) <= depth:
        return path[0] if path[0] == "wallpapers" else None
    key = path[depth]
    return None if key == ANY_KEY else f"{path[0]}.{key}"


def _aliases(function: ast.AST) -> dict[str, list[str]]:
    """Locals that stand for a path into ``configuration``, so ``palette["x"]`` resolves.

    ``palette = configuration["palette"][theme]`` is the one that matters; the same pass
    picks up ``two_step = plymouth_configuration["two-step"]``, which is what lets a field
    be reported under its INI section.
    """
    found: dict[str, list[str]] = {}
    for node in ast.walk(function):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or not isinstance(node.value, ast.Subscript):
            continue
        path = _subscript_path(node.value)
        base = _base_name(node.value)
        if base == "configuration" and path:
            found[target.id] = path
        elif base is not None and path:
            found.setdefault(f"@{target.id}", path)
    return found


def _factor(parent: ast.BinOp, child: ast.AST, numbers: dict[str, float]) -> str | None:
    """``× 0.714`` for the operand this value is multiplied by.

    A named ratio is resolved through ``numbers`` rather than printed as its name: the point
    of the column is the number kitty actually writes, and ``× FONT_SIZE_RATIO`` sends the
    reader back to the source this report exists to save them reading.
    """
    other = parent.right if parent.left is child else parent.left
    if isinstance(other, ast.Constant) and isinstance(other.value, int | float):
        return f"× {other.value}"
    if isinstance(other, ast.Name):
        return f"× {numbers.get(other.id, other.id)}"
    return None


def _embeds(joined: ast.JoinedStr) -> bool:
    """Whether an f-string surrounds the value with anything but quoting.

    ``f\'"{colour}"\'`` in patch_dunst is the INI's quoting and says nothing; the Pango span
    in the same file's ``format`` genuinely carries the colour inside a longer string, and
    that difference is the whole use of the column.
    """
    literal = "".join(
        part.value
        for part in joined.values
        if isinstance(part, ast.Constant) and isinstance(part.value, str)
    )
    return bool(literal.strip().strip("\"'").strip())


def _climb(
    node: ast.AST, parents: dict[ast.AST, ast.AST], numbers: dict[str, float]
) -> tuple[ast.AST, list[str]]:
    """Walk up to the node that names a field, collecting what happened on the way."""
    how: list[str] = []
    current = node
    while current in parents:
        parent = parents[current]
        if isinstance(parent, ast.BinOp):
            factor = _factor(parent, current, numbers)
            if factor:
                how.append(factor)
        elif isinstance(parent, ast.JoinedStr):
            if _embeds(parent) and HOW_EMBEDDED not in how:
                how.append(HOW_EMBEDDED)
        elif isinstance(parent, ast.Compare | ast.IfExp):
            how.append("selects")
        elif isinstance(parent, ast.Dict | ast.Assign | ast.keyword | ast.Return):
            return parent, how
        current = parent
    return current, how


def _field(holder: ast.AST, child: ast.AST, aliases: dict[str, list[str]]) -> str | None:
    """The field name ``holder`` assigns ``child`` to, in the target format's vocabulary."""
    if isinstance(holder, ast.keyword):
        return holder.arg
    if isinstance(holder, ast.Dict):
        for key, value in zip(holder.keys, holder.values, strict=True):
            if value is child and isinstance(key, ast.Constant):
                return str(key.value).lstrip("-") if isinstance(key.value, str) else None
        return None
    if isinstance(holder, ast.Assign) and len(holder.targets) == 1:
        target = holder.targets[0]
        if isinstance(target, ast.Subscript):
            path = _subscript_path(target)
            prefix = aliases.get(f"@{_base_name(target)}", [])
            return ".".join([*prefix, *path]) if path else None
    return None


def _carriers(
    function: ast.AST, parents: dict[ast.AST, ast.AST], aliases: dict[str, list[str]],
    numbers: dict[str, float],
) -> dict[str, list[tuple[str, list[str]]]]:
    """Locals that hold a theme value on its way to a field.

    ``dunst_font_size = round(configuration["font"]["size"] * 0.714)`` is read three lines
    before it is written, and a walk that only looked at the assignment holding the field
    would report dunst as setting a font it never scaled.
    """
    found: dict[str, list[tuple[str, list[str]]]] = {}
    for node in ast.walk(function):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        for inner in ast.walk(node.value):
            value = _theme_value(inner, aliases)
            # `theme = configuration["state"]["theme"]` names which half of the palette to
            # read, and is then subscripted a dozen times. Carrying it would report every
            # colour in the file as a second landing of `state.theme`.
            if value and value != "state.theme":
                _holder, how = _climb(inner, parents, numbers)
                found.setdefault(target.id, []).append((value, how))
    return found


def _reads(
    node: ast.AST, aliases: dict[str, list[str]],
    carriers: dict[str, list[tuple[str, list[str]]]],
) -> list[tuple[str, list[str]]]:
    """The theme values ``node`` stands for: read directly, or carried by a local."""
    value = _theme_value(node, aliases)
    if value:
        return [(value, [])]
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
        return carriers.get(node.id, [])
    return []


def _function_records(
    stem: str, function: ast.FunctionDef, parents: dict[ast.AST, ast.AST],
    numbers: dict[str, float],
) -> list[Usage]:
    """Every theme value read inside one function, with the field it lands in."""
    target = TARGETS.get((stem, function.name))
    if target is None:
        return []
    aliases = _aliases(function)
    carriers = _carriers(function, parents, aliases, numbers)
    records = []
    for node in ast.walk(function):
        for value, carried in _reads(node, aliases, carriers):
            holder, how = _climb(node, parents, numbers)
            field = _field(holder, _child_of(node, holder, parents), aliases)
            if field is None:
                continue
            steps = list(dict.fromkeys(carried + how))
            records.append(
                Usage(
                    value=value,
                    app=APPS[stem],
                    target=target,
                    key=field,
                    how=", ".join(steps) or HOW_DIRECT,
                    source=f"helper/{stem}.py:{node.lineno}",
                )
            )
    return records


def _child_of(node: ast.AST, holder: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.AST:
    """The ancestor of ``node`` that is a direct child of ``holder``."""
    current = node
    while current in parents and parents[current] is not holder:
        current = parents[current]
    return current


def _module_constant(tree: ast.AST, name: str) -> Any | None:
    """A module-level literal, so a table like ``ANSI_SLOTS`` is read rather than restated."""
    for node in tree.body:
        if isinstance(node, ast.Assign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id == name for t in targets):
                try:
                    return ast.literal_eval(node.value)
                except ValueError:
                    return None
    return None


def _module_numbers(tree: ast.AST) -> dict[str, float]:
    """Module-level numeric constants, so a named ratio prints as the number it is."""
    numbers = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            value = node.value
            if (
                isinstance(target, ast.Name)
                and isinstance(value, ast.Constant)
                and isinstance(value.value, int | float)
            ):
                numbers[target.id] = value.value
    return numbers


#: Patchers that pin the palette variant instead of following ``state.theme``. The walker
#: cannot see this: ``render_theme(configuration, staged, PALETTE_VARIANT, name)`` passes the
#: variant as an argument, so inside the function it is an ordinary parameter. Declared here
#: with the fact it stands for, and asserted in tests/test_list_palette.py.
PINNED_VARIANT: dict[str, str] = {"patch_plymouth": "dark"}


def _patcher_records(stem: str) -> list[Usage]:
    tree = ast.parse((REPO_ROOT / "helper" / f"{stem}.py").read_text())
    parents = _parents(tree)
    numbers = _module_numbers(tree)
    records = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            records += _function_records(stem, node, parents, numbers)
    records += _expanded(stem, tree)

    variant = PINNED_VARIANT.get(stem)
    if variant is None:
        return records
    return [
        record._replace(how=f"{record.how}, always {variant}")
        if f"always {variant}" not in record.how
        else record
        for record in records
    ]


# --------------------------------------------------- tables the plain walk cannot reach
#
# Three patchers drive fields from a module-level table rather than writing each one out.
# The tables are read from the source with ``ast.literal_eval`` -- never copied here -- so
# these expanders describe the *shape* of the loop and nothing else. A row added to
# ``ANSI_SLOTS`` shows up in this report without anything below changing.


def _kitty_ansi(tree: ast.AST) -> list[Usage]:
    """kitty's sixteen ANSI slots: slot *i* takes the first token, slot *i + 8* the second."""
    slots = _module_constant(tree, "ANSI_SLOTS") or ()
    records = []
    for index, (_name, normal, bright) in enumerate(slots):
        for offset, token in ((0, normal), (8, bright)):
            records.append(
                Usage(
                    value=f"palette.{token}",
                    app="kitty",
                    target=TARGETS[("patch_kitty", "kitty_configuration")],
                    key=f"color{index + offset}",
                    how=HOW_DIRECT,
                    source="helper/patch_kitty.py:ANSI_SLOTS",
                )
            )
    return records


def _gtk_roles(tree: ast.AST) -> list[Usage]:
    """gtk names a role per token, then aliases libadwaita's own colours onto the roles."""
    roles = _module_constant(tree, "ROLES") or {}
    adwaita = _module_constant(tree, "ADWAITA_COLOURS") or {}
    rules = _module_constant(tree, "RULES") or ()
    css = TARGETS[("patch_gtk", "gtk_css")]
    records = [
        Usage(f"palette.{token}", "gtk", css, f"@define-color {role}", HOW_DIRECT,
              "helper/patch_gtk.py:ROLES")
        for role, token in roles.items()
    ]
    records += [
        Usage(f"palette.{roles[role]}", "gtk", css, name, f"{HOW_ALIASED} `{role}`",
              "helper/patch_gtk.py:ADWAITA_COLOURS")
        for name, role in adwaita.items()
        if role in roles
    ]
    for selector, background, foreground in rules:
        for role, property_name in ((background, "background-color"), (foreground, "color")):
            if role in roles:
                records.append(
                    Usage(f"palette.{roles[role]}", "gtk", css,
                          f"{selector} {{ {property_name} }}", f"{HOW_ALIASED} `{role}`",
                          "helper/patch_gtk.py:RULES")
                )
    return records


def _plymouth_assets(tree: ast.AST) -> list[Usage]:
    """The boot splash's images are re-rendered per token, always from the dark palette."""
    target = TARGETS[("patch_plymouth", "render_assets")]
    records = []
    for filename, _size, token in _module_constant(tree, "SOLID_ASSETS") or ():
        records.append(Usage(f"palette.{token}", "plymouth", target, filename,
                             f"{HOW_RENDERED}, always dark", "helper/patch_plymouth.py:SOLID_ASSETS"))
    for filename, _size, token, *_rest in _module_constant(tree, "GLYPH_ASSETS") or ():
        records.append(Usage(f"palette.{token}", "plymouth", target, filename,
                             f"{HOW_RENDERED}, always dark", "helper/patch_plymouth.py:GLYPH_ASSETS"))
    return records


EXPANDERS = {
    "patch_kitty": _kitty_ansi,
    "patch_gtk": _gtk_roles,
    "patch_plymouth": _plymouth_assets,
}


def _expanded(stem: str, tree: ast.AST) -> list[Usage]:
    expander = EXPANDERS.get(stem)
    return expander(tree) if expander else []


# ------------------------------------------------------- consumers that are not patchers


def _qtile_records() -> list[Usage]:
    """qtile is read live rather than patched, so its config.py *is* the consumer.

    The palette subscript is attributed to the innermost call that holds it -- a nested
    ``Call`` is its own consumer -- which is what keeps a widget's colour off the bar's row.
    """
    path = REPO_ROOT / "configuration" / "qtile" / "config.py"
    tree = ast.parse(path.read_text())
    target = "configuration/qtile/config.py"
    seen: dict[tuple[str, str, str], int] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        consumer = ast.unparse(node.func)
        if consumer == "dict":
            consumer = "widget_defaults"
        for keyword in node.keywords:
            if keyword.arg is None or isinstance(keyword.value, ast.Call):
                continue
            for lineno, value in _qtile_values(keyword.value):
                seen.setdefault((f"{consumer}({keyword.arg}=)", value, target), lineno)
    return [
        Usage(value, "qtile", target, key, HOW_DIRECT, f"configuration/qtile/config.py:{lineno}")
        for (key, value, target), lineno in sorted(seen.items(), key=lambda item: item[1])
    ]


def _qtile_values(node: ast.AST) -> list[tuple[int, str]]:
    """(lineno, value) for theme reads under ``node``, not descending into nested calls."""
    found = []

    def recurse(current: ast.AST) -> None:
        value = _theme_value(current, {})
        if value:
            found.append((getattr(current, "lineno", 0), value))
        for child in ast.iter_child_nodes(current):
            if not isinstance(child, ast.Call):
                recurse(child)

    recurse(node)
    return found


def _web_greeter_records() -> list[Usage]:
    """Each theme's ``theme.json`` names its own roles; the patcher writes them as CSS vars.

    The font size is the one theme value that does **not** reach this file: ``theme_variables``
    merges ``theme.json#font_overrides`` over the configuration's font, and the shipped theme
    pins a size. Recorded as ``pinned`` rather than omitted, because "the login screen ignores
    your font size" is the useful half of the answer.
    """
    themes_dir = REPO_ROOT / "configuration" / "web-greeter" / "themes"
    records = []
    for theme_dir in sorted(themes_dir.iterdir()):
        theme_json = theme_dir / "theme.json"
        if theme_dir.name.startswith("_") or not theme_json.is_file():
            continue
        try:
            manifest = json.loads(theme_json.read_text())
        except json.JSONDecodeError:
            continue
        target = f"configuration/web-greeter/themes/{theme_dir.name}/theme.css"
        source = f"configuration/web-greeter/themes/{theme_dir.name}/theme.json"
        records += [
            Usage(f"palette.{token}", "web-greeter", target, f"--{role}", HOW_DIRECT,
                  f"{source}#role_map")
            for role, token in manifest.get("role_map", {}).items()
        ]
        overrides = manifest.get("font_overrides", {})
        for field, name in (("family", "--font-family"), ("size", "--font-size")):
            pinned = field in overrides
            records.append(
                Usage(f"font.{field}", "web-greeter", target, name,
                      f"{HOW_PINNED} to {overrides[field]}" if pinned else HOW_DIRECT,
                      f"{source}#font_overrides" if pinned else "helper/patch_web_greeter.py:68")
            )
        if "wallpaper_key" in manifest:
            records.append(
                Usage(f"wallpapers.{manifest['wallpaper_key']}", "web-greeter", target,
                      "--wallpaper-url", f"{HOW_RENDERED}, symlinked as wallpaper.png",
                      "helper/patch_web_greeter.py:96")
            )
    return records


# ------------------------------------------------------------------------- vscode
#
# VSCode's mapping is not in its source: patch_vsc resolves every colour in a stock theme
# perceptually against the active palette. Replaying the *pure* half of that machinery
# reproduces it exactly without running the patcher, writing a file, or touching the user's
# settings.json.


def _vsc_matches(config: dict) -> dict[str, list[tuple[str, str, float]]]:
    """``mode -> [(vscode key, token, ΔE)]`` for every colour in the stock themes."""
    if not _HAVE_COLOUR or not config or "palette" not in config:
        return {}
    directory = str(REPO_ROOT / "configuration" / "vscode")
    try:
        defaults = patch_vsc.load_default_themes(directory)
    except OSError:
        return {}
    palette_map = patch_vsc.build_palette_map(config["palette"])
    matches = {}
    for mode in patch_vsc.MODES:
        rows = []
        for key, value in sorted(defaults[mode].get("colors", {}).items()):
            if not isinstance(value, str) or not value.startswith("#"):
                continue
            # The engine strips the alpha itself, so this no longer keeps its own copy of
            # that rule -- which is where the two implementations had drifted.
            found = color_match.nearest(
                value, color_match.filter_candidates(key, palette_map[mode])
            )
            if found is not None:
                rows.append((key, found.label, found.delta))
        matches[mode] = rows
    return matches


def _vsc_section(config: dict) -> str:
    lines = ["### vscode — perceptual nearest match (`helper/patch_vsc.py`)", ""]
    matches = _vsc_matches(config)
    if not matches:
        lines.append(
            "_Needs the `colour` library and an active `~/.config/config.json`; "
            "skipping the enumeration._"
        )
        return "\n".join(lines)
    lines.append(
        "Every colour in the stock theme is matched against the active palette in CAM16-UCS "
        "and replaced by the nearest token, so these are resolved rather than declared. "
        "`background` is excluded as a candidate for selection, highlight, hover, focus, "
        "drop, match and range backgrounds, which would otherwise become invisible."
    )
    for mode, rows in matches.items():
        lines += ["", f"#### `{mode}` — {len(rows)} keys "
                      f"(`workbench.colorCustomizations` in `settings.json`)", ""]
        lines.append("| VSCode key | Token | ΔE |")
        lines.append("| --- | --- | --- |")
        lines += [
            f"| `{_escape(key)}` | `{_escape(token)}` | {delta:.1f} |"
            for key, token, delta in rows
        ]
    return "\n".join(lines)


# ----------------------------------------------------------------- the two usage views


def usages() -> list[Usage]:
    """Every theme value landing, from the repository alone. Needs no install."""
    records: list[Usage] = []
    for stem in sorted(APPS):
        records += _patcher_records(stem)
    records += _qtile_records()
    records += _web_greeter_records()
    return records


def _usage_by_value_section(records: list[Usage]) -> str:
    lines = ["### Theme value → usage", ""]
    lines.append(
        "What a theme sets, and every field that carries it. `xorg` is absent because it "
        "reads monitor geometry and no theme value at all."
    )
    for value in sorted({record.value for record in records}):
        rows = sorted(r for r in records if r.value == value)
        lines += ["", f"#### `{value}`", "", "| App | Target | Field | How | Declared |",
                  "| --- | --- | --- | --- | --- |"]
        lines += [
            f"| {_escape(r.app)} | `{_escape(r.target)}` | `{_escape(r.key)}` "
            f"| {_escape(r.how)} | `{_escape(r.source)}` |"
            for r in rows
        ]
    return "\n".join(lines)


def _usage_by_target_section(records: list[Usage]) -> str:
    lines = ["### Configuration file → theme values", ""]
    lines.append("The same records, keyed by the file each value lands in.")
    for target in sorted({record.target for record in records}):
        rows = sorted((r for r in records if r.target == target), key=lambda r: (r.key, r.value))
        app = rows[0].app
        lines += ["", f"#### `{target}` ({app})", "", "| Field | Value | How |",
                  "| --- | --- | --- |"]
        lines += [
            f"| `{_escape(r.key)}` | `{_escape(r.value)}` | {_escape(r.how)} |" for r in rows
        ]
    return "\n".join(lines)


# ----------------------------------------------------------------- drift report


def _pairs(relative: str, pattern: str) -> list[tuple[str, str]]:
    """``(local name, hex)`` from a generated config, or nothing if it is not written yet.

    Every path here is gitignored output, so on a fresh clone -- before the first theme
    switch -- none of them exist. Skipping keeps the drift report from blocking the rest of
    the document, which needs no install at all.
    """
    path = REPO_ROOT / relative
    try:
        text = path.read_text()
    except OSError:
        return []
    return [match.groups() for match in re.finditer(pattern, text, re.MULTILINE)]


def _dunst_pairs() -> list[tuple[str, str]]:
    template = "configuration/dunst/dunstrc.template"
    pairs = _pairs(template, r'^\s*(\w+)\s*=\s*"?(#[0-9a-fA-F]{6})')
    spans = _pairs(template, r"()foreground='(#[0-9a-fA-F]{6})'")
    return pairs + [("urgency span", hex_value) for _, hex_value in spans]


#: Where hex is hardcoded *outside* the palette: the tracked templates.
#:
#: Not the patcher outputs, which is what this read before. Every value in kitty.conf and
#: rofi/theme_config.rasi was written from the palette moments earlier, so reverse-mapping them
#: reported `exact` for all twenty-six and said nothing at all; those two files are generated
#: whole, have no template, and so have no drift to report. The three that remain each keep
#: hand-written settings beside palette-derived ones, and it is the template's own stock hex
#: that is the drift.
#:
#: Reading tracked files is also what lets `gendocs.py` run on a clone where the installer has
#: not: the outputs are gitignored, so reading them raised FileNotFoundError and took the whole
#: script -- and the pre-commit gate -- with it.
DRIFT_TOOLS = [
    ("tmux", "configuration/tmux/tmux.conf.template",
     lambda: _pairs("configuration/tmux/tmux.conf.template",
                    r"^(color\d+)\s*=\s*(#[0-9a-fA-F]{6})")),
    ("starship", "configuration/starship/starship.toml.template",
     lambda: _pairs("configuration/starship/starship.toml.template",
                    r'^(color\d+)\s*=\s*"(#[0-9a-fA-F]{6})"')),
    ("dunst", "configuration/dunst/dunstrc.template", _dunst_pairs),
]


def _drift_section(config: dict) -> str:
    lines = ["### Drift report — hardcoded hex vs. nearest palette token", ""]
    if not config or "palette" not in config:
        lines.append("_No active palette available; skipping reverse-mapping._")
        return "\n".join(lines)

    theme = config.get("state", {}).get("theme", "dark")
    palette_variant = config["palette"].get(theme, {})
    lines.append(
        f"Each template below hardcodes hex outside the palette. Colors are matched "
        f"against "
        f"the active **{theme}** palette"
        + (" (CAM16-UCS ΔE)." if _HAVE_COLOUR else " (exact match only — `colour` not installed).")
    )
    lines.append("")

    exact_lookup = {v.lower(): k for k, v in palette_variant.items()}
    candidates = (color_match.build_palette_map({"one": palette_variant})["one"]
                  if _HAVE_COLOUR else None)

    for tool, rel_path, extractor in DRIFT_TOOLS:
        rows = list(dict.fromkeys(extractor()))
        lines += [f"#### {tool} (`{rel_path}`)", ""]
        if not rows:
            lines += ["_No hardcoded hex._", ""]
            continue
        lines += ["| Local name | Hex | Nearest token | ΔE |", "| --- | --- | --- | --- |"]
        for label, hex_value in rows:
            exact = exact_lookup.get(hex_value.lower())
            if exact is not None:
                token, delta = exact, "exact"
            elif _HAVE_COLOUR:
                found = color_match.nearest(hex_value, candidates)
                token, delta = found.label, f"{found.delta:.1f}"
            else:
                token, delta = "—", "drift"
            lines.append(f"| `{_escape(label)}` | `{hex_value}` | `{_escape(token)}` | {delta} |")
        lines.append("")
    return "\n".join(lines).rstrip()


# ----------------------------------------------------------------------------- API


def generate_markdown() -> str:
    """Return the markdown body for the PALETTE block in ``docs/palette-reference.md``."""
    config = _load_active_config()
    records = usages()
    return "\n\n".join([
        _palette_section(config),
        _usage_by_value_section(records),
        _usage_by_target_section(records),
        _vsc_section(config),
        _drift_section(config),
    ])


def _filtered(records: list[Usage], arguments: argparse.Namespace) -> list[Usage]:
    if arguments.value:
        needle = arguments.value
        records = [r for r in records if needle in (r.value, r.value.split(".", 1)[-1])]
    if arguments.app:
        records = [r for r in records if r.app == arguments.app]
    if arguments.file:
        needle = arguments.file.replace(os.path.expanduser("~"), "~")
        records = [r for r in records if needle in r.target]
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--value", help="one theme value, e.g. `highlight` or `font.size`")
    parser.add_argument("--app", help="one application, e.g. `dunst`")
    parser.add_argument("--file", help="one target configuration file")
    arguments = parser.parse_args(argv)

    if not any((arguments.value, arguments.app, arguments.file)):
        print(generate_markdown())
        return 0

    # vscode's mapping is resolved perceptually rather than declared, so it lives in its own
    # section instead of the record list -- but "--app vscode" is the obvious way to ask for
    # it, and answering "no theme value matches that" would be plainly false.
    if arguments.app == "vscode":
        print(_vsc_section(_load_active_config()))
        return 0

    records = _filtered(usages(), arguments)
    if not records:
        print("No theme value matches that.", file=sys.stderr)
        return 1
    # Asking about a file is asking what is *in* it, so answer in that shape; asking about a
    # value or an app is asking where it goes.
    section = _usage_by_target_section if arguments.file else _usage_by_value_section
    print(section(records))
    return 0


if __name__ == "__main__":
    sys.exit(main())
