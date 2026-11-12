"""List every keyboard binding configured across the tools in this repo.

Statically parses the qtile, vim, tmux, and qutebrowser configurations under
``configuration/`` and emits a markdown overview grouped by tool. Bindings that the
configs generate dynamically (qtile's per-monitor group/screen chords, VT switches) and
the still-active upstream defaults of vim/tmux/qutebrowser are summarised from curated,
hardcoded tables — those do not appear literally in the config files. ``generate_markdown``
returns the body that ``gendocs.py`` injects into ``docs/keybindings.md``; running the
module prints the same body to stdout.
"""

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Human-readable labels for X11 modifier tokens. ``mod`` resolves to ``mod4`` via the
# module-level assignment in the qtile config, then maps to "Super" here.
MOD_LABELS = {
    "mod4": "Super",
    "mod1": "Alt",
    "control": "Ctrl",
    "shift": "Shift",
    "lock": "Lock",
}


def _escape(text: str) -> str:
    """Make a string safe to drop into a markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _code(text: str) -> str:
    return f"`{_escape(text)}`"


# --------------------------------------------------------------------------- qtile


def _resolve_string_assignments(tree: ast.Module) -> dict:
    """Collect module-level ``name = "literal"`` assignments (to resolve ``mod``)."""
    names = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            names[node.targets[0].id] = node.value.value
    return names


def _render_modifiers(node: ast.AST, names: dict) -> list:
    if not isinstance(node, ast.List):
        return []
    parts = []
    for element in node.elts:
        if isinstance(element, ast.Name):
            value = names.get(element.id, element.id)
        elif isinstance(element, ast.Constant):
            value = str(element.value)
        else:
            value = ast.unparse(element)
        parts.append(MOD_LABELS.get(value, value))
    return parts


def _qtile_bindings():
    """Return (rows, dynamic_count) for literal qtile Key/KeyChord bindings.

    ``rows`` are ``(lineno, combo, action, description)`` for bindings whose trigger key
    is a string literal. Bindings whose key is templated (loop-generated) are counted in
    ``dynamic_count`` and described separately by the curated family summary.
    """
    path = REPO_ROOT / "configuration" / "qtile" / "config.py"
    tree = ast.parse(path.read_text())
    names = _resolve_string_assignments(tree)

    rows = []
    dynamic_count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        kind = node.func.id
        if kind not in ("Key", "KeyChord") or len(node.args) < 2:
            continue

        key_node = node.args[1]
        if not (isinstance(key_node, ast.Constant) and isinstance(key_node.value, str)):
            dynamic_count += 1
            continue

        modifiers = _render_modifiers(node.args[0], names)
        combo = " + ".join(modifiers + [key_node.value])

        keywords = {kw.arg: kw.value for kw in node.keywords}
        description = ""
        for field in ("desc", "name"):
            value = keywords.get(field)
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                description = value.value
                break

        if kind == "Key":
            action = ast.unparse(node.args[2]) if len(node.args) > 2 else ""
        else:  # KeyChord — the third positional is a (often dynamic) sub-key list
            name = keywords.get("name")
            label = name.value if isinstance(name, ast.Constant) else "chord"
            action = f"chord → {label}"

        rows.append((node.lineno, combo, action, description))

    rows.sort(key=lambda row: row[0])
    return rows, dynamic_count


def _qtile_section() -> str:
    rows, dynamic_count = _qtile_bindings()
    lines = ["### qtile (`configuration/qtile/config.py`)", ""]
    lines.append("| Keys | Action | Description |")
    lines.append("| --- | --- | --- |")
    for _lineno, combo, action, description in rows:
        lines.append(f"| {_code(combo)} | {_code(action)} | {_escape(description)} |")
    lines.append("")
    lines.append(
        "Generated families "
        f"({dynamic_count} templated bindings the config builds in loops, "
        "one set per connected monitor):"
    )
    lines.append("")
    lines.append(
        "- **VT switching** — `Ctrl + Alt + F1` … `F7` switch to virtual terminals "
        "1–7 (Wayland backend only)."
    )
    lines.append(
        "- **`Super + s` → switch screen focus** — then `j` / `k` / `l` / `;` "
        "(one per monitor) focuses that screen."
    )
    lines.append(
        "- **`Super + f` → switch group** — then `j` / `k` / `l` / `;` jumps to a group "
        "on the active screen."
    )
    lines.append(
        "- **`Super + d` → move to group** — then `j` / `k` / `l` / `;` moves the "
        "focused window to that group."
    )
    lines.append("")
    lines.append(
        "qtile has no built-in default keybindings beyond what this config defines, so "
        "the table above is exhaustive for static bindings."
    )
    return "\n".join(lines)


# ----------------------------------------------------------------------------- vim

VIM_MAP_RE = re.compile(
    r"^\s*(map|nmap|imap|vmap|xmap|smap|omap|nnoremap|inoremap|vnoremap|noremap)"
    r"\s+(\S+)\s+(.+?)\s*$"
)


def _vim_section() -> str:
    path = REPO_ROOT / "configuration" / "vim" / ".vimrc"
    lines = ["### vim (`configuration/vim/.vimrc`)", ""]
    lines.append("| Command | Keys | Maps to |")
    lines.append("| --- | --- | --- |")
    for raw in path.read_text().splitlines():
        if raw.lstrip().startswith('"'):
            continue
        match = VIM_MAP_RE.match(raw)
        if not match:
            continue
        command, lhs, rhs = match.groups()
        lines.append(f"| `{command}` | {_code(lhs)} | {_code(rhs)} |")
    lines.append("")
    lines.append(
        "These override a handful of bindings; vim's hundreds of built-in defaults "
        "(`i` insert, `:w` write, `dd` delete line, `/` search, `gg` / `G` jump, "
        "`u` undo, …) remain active. Full list: `:help index`."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------- tmux

TMUX_BIND_RE = re.compile(r"^\s*(?:bind|bind-key)\b\s+(?:-\S+\s+)*(\S+)\s+(.*)$")


def _tmux_section() -> str:
    path = REPO_ROOT / "configuration" / "tmux" / "tmux.conf"
    text = path.read_text()
    prefix_override = re.search(r"^\s*set\b.*\bprefix\b\s+(\S+)", text, re.MULTILINE)
    prefix = prefix_override.group(1) if prefix_override else "C-b"

    lines = ["### tmux (`configuration/tmux/tmux.conf`)", ""]
    lines.append(f"Prefix: `{prefix}` (tmux default — not overridden here).")
    lines.append("")
    lines.append("| Keys | Command |")
    lines.append("| --- | --- |")
    for raw in text.splitlines():
        if raw.lstrip().startswith("#"):
            continue
        match = TMUX_BIND_RE.match(raw)
        if not match:
            continue
        key, command = match.groups()
        lines.append(f"| {_code(f'{prefix} {key}')} | {_code(command)} |")
    lines.append("")
    lines.append(
        "tmux ships an extensive default key table that stays active, e.g. "
        f"`{prefix} c` new window, `{prefix} %` / `{prefix} \"` split, "
        f"`{prefix} d` detach, `{prefix} [` copy mode, `{prefix} ,` rename window. "
        "Full list: the *DEFAULT KEY BINDINGS* section of `man tmux`."
    )
    return "\n".join(lines)


# -------------------------------------------------------------------- qutebrowser

QUTE_BIND_RE = re.compile(
    r"""config\.bind\(\s*(['"])(?P<keys>.*?)\1\s*,\s*(['"])(?P<command>.*?)\3"""
)


def _qutebrowser_section() -> str:
    path = REPO_ROOT / "configuration" / "qutebrowser" / "config.py"
    lines = ["### qutebrowser (`configuration/qutebrowser/config.py`)", ""]
    lines.append("| Keys | Command |")
    lines.append("| --- | --- |")
    for raw in path.read_text().splitlines():
        if raw.lstrip().startswith("#"):
            continue
        match = QUTE_BIND_RE.search(raw)
        if not match:
            continue
        lines.append(
            f"| {_code(match.group('keys'))} | {_code(match.group('command'))} |"
        )
    lines.append("")
    lines.append(
        "Only the explicit overrides above are added; qutebrowser's full default keymap "
        "stays active, e.g. `o` / `O` open, `f` hint, `H` / `L` back / forward, "
        "`gt` tab select, `/` search, `:` command mode. Full list: "
        "<https://qutebrowser.org/doc/help/configuring.html> and `:bind` in the browser."
    )
    return "\n".join(lines)


# ----------------------------------------------------------------------------- API


def generate_markdown() -> str:
    """Return the markdown body for the KEYBINDINGS block in ``docs/keybindings.md``."""
    sections = [
        _qtile_section(),
        _vim_section(),
        _tmux_section(),
        _qutebrowser_section(),
    ]
    note = (
        "> rofi and xorg configure action names and the keyboard layout rather than "
        "discrete shortcuts, so they are not listed here. The rofi window switcher "
        "(`Super + Shift + r`) prefixes each entry with its group as `[N]`; groups map "
        "to screens in blocks of four (groups 1–4 → screen 1, 5–8 → screen 2, …), so the "
        "prefix doubles as a screen hint."
    )
    return "\n\n".join(sections + [note])


if __name__ == "__main__":
    print(generate_markdown())
