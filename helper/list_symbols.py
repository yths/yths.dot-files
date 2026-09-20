"""List the symbol and string vocabulary, what falls back to what, and who reads each entry.

Three columns that answer the three questions the vocabulary raises. *What does this key
default to* is the ASCII stand-in in ``helper/symbols.py``. *What does the shipped bundle make
it* is the override in ``assets/default/config.json`` -- usually a Nerd Font glyph, which is
printed as its codepoint because the character itself is invisible in an editor, a diff and a
terminal without the font. *Who reads it* is grepped from the tree rather than recorded, so a
key that loses its last consumer shows up as an empty cell instead of staying in the table.

``generate_markdown`` returns the body that ``gendocs.py`` injects into ``docs/symbols.md``;
running the module prints the same body. Everything here is derived from the repository, so
the block is identical on every machine -- unlike the palette's, which reads the active
install.
"""

import json
import re
from pathlib import Path

try:
    from helper import symbols
except ImportError:
    import symbols

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Where a key may legitimately be read. Everything else in the tree is documentation or a
#: test, and a key named only there has no consumer.
SEARCH_ROOTS = ("configuration", "helper", "install.py")

#: Files that mention keys without consuming them: the vocabulary itself declares them all,
#: and the bundle overrides them all, so counting either as a consumer would make the
#: "read by nothing" check unable to fire.
NOT_CONSUMERS = ("helper/symbols.py", "helper/list_symbols.py")


def _escape(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def _printable(value: str | tuple[str, ...]) -> str:
    """A value as something a reader can see, with codepoints for anything invisible."""
    rungs = value if isinstance(value, tuple) else (value,)
    rendered = []
    for rung in rungs:
        if rung.isascii() and rung.isprintable():
            rendered.append(f"`{rung}`" if rung.strip() else "`&nbsp;`")
        else:
            rendered.append(" ".join(f"U+{ord(character):04X}" for character in rung))
    return ", ".join(rendered)


def _sources() -> dict[str, str]:
    """Every file a key could be read from, by repository-relative path."""
    found = {}
    for root in SEARCH_ROOTS:
        path = REPO_ROOT / root
        paths = [path] if path.is_file() else sorted(path.rglob("*"))
        for candidate in paths:
            if not candidate.is_file() or candidate.suffix not in (".py", ".js", ".json"):
                continue
            relative = candidate.relative_to(REPO_ROOT).as_posix()
            if relative in NOT_CONSUMERS or "/themes/" in relative:
                continue
            try:
                found[relative] = candidate.read_text()
            except (OSError, UnicodeDecodeError):
                continue
    return found


#: Namespaces read wholesale rather than key by key, with the file that does it. A grep for
#: the quoted key cannot see these: patch_plymouth builds ``plymouth.<mode>.<field>`` from a
#: section table, and the login screen's whole vocabulary is handed to JavaScript as one JSON
#: object. Recorded rather than guessed, so "read by nothing" stays a real finding.
NAMESPACE_CONSUMERS = {
    "plymouth.": "helper/patch_plymouth.py",
    "greeter.": "helper/patch_web_greeter.py",
}


def consumers(sources: dict[str, str] | None = None) -> dict[str, list[str]]:
    """Which files read each key, by grepping for the quoted key."""
    sources = sources if sources is not None else _sources()
    found: dict[str, list[str]] = {}
    for key in list(symbols.SYMBOLS) + list(symbols.STRINGS):
        # The greeter spells its keys without the namespace, because its theme.json always
        # has; patch_web_greeter strips the prefix on the way out.
        needles = {key, key.removeprefix("greeter.")} if key.startswith("greeter.") else {key}
        paths = {
            path
            for path, body in sources.items()
            if any(re.search(rf"""['"]{re.escape(n)}['"]""", body) for n in needles)
        }
        paths.update(
            path
            for prefix, path in NAMESPACE_CONSUMERS.items()
            if key.startswith(prefix)
        )
        found[key] = sorted(paths)
    return found


def unread(sources: dict[str, str] | None = None) -> list[str]:
    """Keys nothing reads. A declared symbol no surface draws is dead vocabulary."""
    return sorted(key for key, paths in consumers(sources).items() if not paths)


def _bundle_overrides() -> dict[str, dict]:
    try:
        bundle = json.loads((REPO_ROOT / "assets/default/config.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {"symbols": {}, "strings": {}}
    return {
        "symbols": bundle.get("symbols") or {},
        "strings": bundle.get("strings") or {},
    }


def _table(vocabulary: dict, overrides: dict, found: dict[str, list[str]]) -> list[str]:
    lines = ["| Key | ASCII default | `assets/default/` | Read by |", "| --- | --- | --- | --- |"]
    for key, default in vocabulary.items():
        override = overrides.get(key)
        shipped = _printable(tuple(override) if isinstance(override, list) else override) \
            if override is not None else "_the default_"
        read_by = ", ".join(f"`{path}`" for path in found[key]) or "—"
        lines.append(
            f"| `{_escape(key)}` | {_printable(default)} | {shipped} | {read_by} |"
        )
    return lines


def generate_markdown() -> str:
    """Return the markdown body for the SYMBOLS block in ``docs/symbols.md``."""
    overrides = _bundle_overrides()
    found = consumers()
    lines = [
        f"### Symbols ({len(symbols.SYMBOLS)})",
        "",
        "Every default is ASCII, so a machine whose font has no private use area still draws "
        "a readable desktop. The shipped bundle overrides them with Nerd Font glyphs, printed "
        "here as codepoints because the characters are invisible without the font.",
        "",
        *_table(symbols.SYMBOLS, overrides["symbols"], found),
        "",
        f"### Strings ({len(symbols.STRINGS)})",
        "",
        "The boot splash's messages are the ones worth knowing about: they were the only part "
        "of the splash a theme could not reach until the vocabulary existed.",
        "",
        *_table(symbols.STRINGS, overrides["strings"], found),
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(generate_markdown())
