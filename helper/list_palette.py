"""Summarise how palette tokens are mapped across the configurations in this repo.

Three views, emitted as markdown:

1. **Palette** — the active ``token -> hex`` table (light/dark) read from
   ``~/.config/config.json``.
2. **Logical role maps** — which semantic token each consumer assigns to which role,
   parsed from ``configuration/qtile/config.py`` (``ast``), every web-greeter
   ``theme.json`` ``role_map``, and the curated plymouth mapping.
3. **Drift report** — tools that hardcode hex *outside* the palette (kitty, tmux,
   starship, dunst, rofi); each color is reverse-mapped to its nearest palette token via
   the perceptual ``closest_color`` machinery reused from ``patch_vsc.py``.

``generate_markdown`` returns the body that ``gendocs.py`` injects into
``docs/palette-reference.md``;
running the module prints the same body to stdout. The role maps are repo-derived and
stable; the hex values and ΔE distances reflect the active install and vary per theme.
"""

import ast
import json
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(os.path.expanduser("~/.config/config.json"))

HEX_RE = re.compile(r"#[0-9a-fA-F]{6}")

try:  # the drift report's perceptual matching reuses patch_vsc + the `colour` library
    import colour
    from patch_vsc import color_str_to_tuple

    _HAVE_COLOUR = True
except ImportError:
    _HAVE_COLOUR = False


def _escape(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def _load_active_config() -> dict:
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
            "a palette. Role maps and the drift structure below are still parsed from the "
            "repo._"
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
    lines.append(
        "_Hex values reflect the active theme bundle and differ per install._"
    )
    return "\n".join(lines)


# --------------------------------------------------------------- qtile role maps


def _palette_token(node: ast.AST) -> str | None:
    """Return the token if ``node`` is ``configuration["palette"][theme]["<token>"]``."""
    if not isinstance(node, ast.Subscript):
        return None
    if not (isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str)):
        return None
    token = node.slice.value
    middle = node.value
    if not isinstance(middle, ast.Subscript):
        return None
    base = middle.value
    if not (
        isinstance(base, ast.Subscript)
        and isinstance(base.slice, ast.Constant)
        and base.slice.value == "palette"
        and isinstance(base.value, ast.Name)
        and base.value.id == "configuration"
    ):
        return None
    return token


def _tokens_without_descending_into_calls(node: ast.AST) -> list:
    """Yield (lineno, token) for palette subscripts under ``node``, stopping at nested
    ``Call`` boundaries so a token is attributed to its own innermost consumer only."""
    found = []

    def recurse(current: ast.AST) -> None:
        token = _palette_token(current)
        if token:
            found.append((getattr(current, "lineno", 0), token))
        for child in ast.iter_child_nodes(current):
            if isinstance(child, ast.Call):
                continue
            recurse(child)

    recurse(node)
    return found


def _qtile_roles() -> list:
    """Return ``(consumer, role, token)`` rows in source order, de-duplicated."""
    path = REPO_ROOT / "configuration" / "qtile" / "config.py"
    tree = ast.parse(path.read_text())

    seen = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        consumer = ast.unparse(node.func)
        if consumer == "dict":
            consumer = "widget_defaults (dict)"
        for keyword in node.keywords:
            if keyword.arg is None or isinstance(keyword.value, ast.Call):
                continue
            for lineno, token in _tokens_without_descending_into_calls(keyword.value):
                key = (consumer, keyword.arg, token)
                if key not in seen:
                    seen[key] = lineno
    return [key for key, _ in sorted(seen.items(), key=lambda item: item[1])]


def _qtile_role_section() -> str:
    lines = ["### qtile role → token (`configuration/qtile/config.py`)", ""]
    lines.append("| Consumer | Role | Token |")
    lines.append("| --- | --- | --- |")
    for consumer, role, token in _qtile_roles():
        lines.append(f"| `{_escape(consumer)}` | `{_escape(role)}` | `{_escape(token)}` |")
    return "\n".join(lines)


# ----------------------------------------------------------- web-greeter role map


def _web_greeter_section() -> str:
    themes_dir = REPO_ROOT / "configuration" / "web-greeter" / "themes"
    lines = ["### web-greeter role → token (`theme.json#role_map`)", ""]
    lines.append("| Theme | CSS role | Token |")
    lines.append("| --- | --- | --- |")
    for theme_dir in sorted(themes_dir.iterdir()):
        theme_json = theme_dir / "theme.json"
        if theme_dir.name.startswith("_") or not theme_json.is_file():
            continue
        try:
            role_map = json.loads(theme_json.read_text()).get("role_map", {})
        except json.JSONDecodeError:
            continue
        for role, token in role_map.items():
            lines.append(
                f"| `{_escape(theme_dir.name)}` | `--{_escape(role)}` | `{_escape(token)}` |"
            )
    return "\n".join(lines)


# ----------------------------------------------------------- plymouth role map


# Curated from helper/patch_plymouth.py — plymouth's INI/asset vocabulary is rendered
# from these tokens, so it cannot be parsed as generically as the qtile config.
PLYMOUTH_ROLES = [
    ("background", "Background*Color, ConsoleLogBackgroundColor, entry & animation fill"),
    ("foreground", "ConsoleLogTextColor, bullet glyph, throbber-01"),
    ("neutral", "ProgressBarBackgroundColor, throbber-02, keyboard & lock glyphs"),
    ("highlight", "capslock glyph"),
]


def _plymouth_section() -> str:
    lines = ["### plymouth token → usage (`helper/patch_plymouth.py`)", ""]
    lines.append("| Token | Rendered into |")
    lines.append("| --- | --- |")
    for token, usage in PLYMOUTH_ROLES:
        lines.append(f"| `{token}` | {_escape(usage)} |")
    return "\n".join(lines)


# ----------------------------------------------------------------- drift report


def _kitty_pairs() -> list:
    path = REPO_ROOT / "configuration" / "kitty" / "current-theme.conf"
    pairs = []
    for raw in path.read_text().splitlines():
        match = re.match(r"^(\S+)\s+(#[0-9a-fA-F]{6})\b", raw)
        if match:
            pairs.append((match.group(1), match.group(2)))
    return pairs


def _tmux_pairs() -> list:
    path = REPO_ROOT / "configuration" / "tmux" / "tmux.conf"
    pairs = []
    for raw in path.read_text().splitlines():
        match = re.match(r"^(color\d+)\s*=\s*(#[0-9a-fA-F]{6})", raw)
        if match:
            pairs.append((match.group(1), match.group(2)))
    return pairs


def _starship_pairs() -> list:
    path = REPO_ROOT / "configuration" / "starship" / "starship.toml"
    pairs = []
    for raw in path.read_text().splitlines():
        match = re.match(r'^(color\d+)\s*=\s*"(#[0-9a-fA-F]{6})"', raw)
        if match:
            pairs.append((match.group(1), match.group(2)))
    return pairs


def _dunst_pairs() -> list:
    path = REPO_ROOT / "configuration" / "dunst" / "dunstrc"
    pairs = []
    for raw in path.read_text().splitlines():
        assignment = re.match(r'^\s*(\w+)\s*=\s*"?(#[0-9a-fA-F]{6})', raw)
        if assignment:
            pairs.append((assignment.group(1), assignment.group(2)))
            continue
        span = re.search(r"foreground='(#[0-9a-fA-F]{6})'", raw)
        if span:
            pairs.append(("urgency span", span.group(1)))
    return pairs


def _rofi_pairs() -> list:
    path = REPO_ROOT / "configuration" / "rofi" / "theme_config.rasi"
    pairs = []
    for raw in path.read_text().splitlines():
        match = re.match(r"^\s*(COLOR\d+):\s*(#[0-9a-fA-F]{6})", raw)
        if match:
            pairs.append((match.group(1), match.group(2)))
    return pairs


DRIFT_TOOLS = [
    ("kitty", "configuration/kitty/current-theme.conf", _kitty_pairs),
    ("tmux", "configuration/tmux/tmux.conf", _tmux_pairs),
    ("starship", "configuration/starship/starship.toml", _starship_pairs),
    ("dunst", "configuration/dunst/dunstrc", _dunst_pairs),
    ("rofi", "configuration/rofi/theme_config.rasi", _rofi_pairs),
]


def _build_candidates(palette_variant: dict) -> list:
    """Pre-compute CAM16-UCS coordinates for every palette token (perceptual path)."""
    candidates = []
    for label, hex_value in palette_variant.items():
        rgb = color_str_to_tuple(hex_value)
        cam16 = colour.XYZ_to_CAM16UCS(colour.sRGB_to_XYZ(rgb))
        candidates.append((label, hex_value, cam16))
    return candidates


def _nearest_token(hex_value: str, candidates: list) -> tuple:
    rgb = color_str_to_tuple(hex_value)
    cam16 = colour.XYZ_to_CAM16UCS(colour.sRGB_to_XYZ(rgb))
    best_label, best_delta = None, float("inf")
    for label, _hex, candidate_cam16 in candidates:
        delta = float(colour.delta_E(cam16, candidate_cam16, method="CAM16-UCS"))
        if delta < best_delta:
            best_label, best_delta = label, delta
    return best_label, best_delta


def _drift_section(config: dict) -> str:
    lines = ["### Drift report — hardcoded hex vs. nearest palette token", ""]
    if not config or "palette" not in config:
        lines.append("_No active palette available; skipping reverse-mapping._")
        return "\n".join(lines)

    theme = config.get("state", {}).get("theme", "dark")
    palette_variant = config["palette"].get(theme, {})
    lines.append(
        f"Each tool below hardcodes hex outside the palette. Colors are matched against "
        f"the active **{theme}** palette"
        + (" (CAM16-UCS ΔE)." if _HAVE_COLOUR else " (exact match only — `colour` not installed).")
    )
    lines.append("")

    exact_lookup = {v.lower(): k for k, v in palette_variant.items()}
    candidates = _build_candidates(palette_variant) if _HAVE_COLOUR else None

    for tool, rel_path, extractor in DRIFT_TOOLS:
        lines.append(f"#### {tool} (`{rel_path}`)")
        lines.append("")
        lines.append("| Local name | Hex | Nearest token | ΔE |")
        lines.append("| --- | --- | --- | --- |")
        for label, hex_value in dict.fromkeys(extractor()):
            exact = exact_lookup.get(hex_value.lower())
            if exact is not None:
                token, delta = exact, "exact"
            elif _HAVE_COLOUR:
                token, distance = _nearest_token(hex_value, candidates)
                delta = f"{distance:.1f}"
            else:
                token, delta = "—", "drift"
            lines.append(
                f"| `{_escape(label)}` | `{hex_value}` | `{_escape(token)}` | {delta} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip()


# ----------------------------------------------------------------------------- API


def generate_markdown() -> str:
    """Return the markdown body for the PALETTE block in ``docs/palette-reference.md``."""
    config = _load_active_config()
    sections = [
        _palette_section(config),
        _qtile_role_section(),
        _web_greeter_section(),
        _plymouth_section(),
        _drift_section(config),
    ]
    return "\n\n".join(sections)


if __name__ == "__main__":
    print(generate_markdown())
