"""How far each recoloured value moved, for the two applications whose colours are resolved.

Most patchers are told which palette token to use. Two are not: VSCode and qutebrowser both
take a stock theme and replace every colour in it with the nearest one the palette has. That
is only a good idea while "nearest" is actually near -- a token 25 ΔE away in CAM16-UCS is a
visibly different colour, and until now nothing said so. A palette that has drifted, lost a
token, or was never meant for a dense editor theme looks exactly like one that fits.

So this reports the distribution rather than a verdict. A large distance means the palette
cannot represent that colour, which is a fact about somebody's design; refusing a commit over
it would be this repository having an opinion about a theme it did not write. The numbers are
evidence to read when something looks wrong.

The palette is read from the bundle under ``assets/`` rather than from
``~/.config/config.json``, the way ``helper/render_preview.py`` already does, so the generated
block is the same on every machine and changes only when the bundle does.
"""

import argparse
import json
import pickle
import statistics
import sys
from pathlib import Path
from typing import Any, NamedTuple

try:
    from helper import color_match, patch_qutebrowser, patch_vsc
    from helper.utils import read_setup
except ImportError:
    import color_match
    import patch_qutebrowser
    import patch_vsc
    from utils import read_setup

REPO_ROOT = Path(__file__).resolve().parent.parent

#: How many of the furthest replacements to name. Enough to see a pattern -- one token
#: absorbing every outlier -- without turning the section into a second enumeration.
WORST = 8


class Replacement(NamedTuple):
    """One colour the patcher replaced, and what it cost."""

    key: str
    original: str
    label: str
    delta: float


def _bundle_palette() -> dict[str, dict[str, str]] | None:
    setup = read_setup()
    path = REPO_ROOT / "assets" / setup["desktop"]["theme"] / "palette.pkl"
    try:
        with path.open("rb") as handle:
            return pickle.load(handle)
    except OSError:
        return None


def vscode_replacements(palette: dict, mode: str) -> list[Replacement]:
    """Every colour in the stock VSCode theme, with the token that replaced it."""
    directory = str(REPO_ROOT / "configuration" / "vscode")
    try:
        theme = patch_vsc.load_default_themes(directory)[mode]
    except OSError:
        return []
    candidates = color_match.build_palette_map(palette)[mode]
    found = []
    for key, value in sorted(theme.get("colors", {}).items()):
        match = color_match.nearest(value, color_match.filter_candidates(key, candidates))
        if match is not None:
            found.append(Replacement(key, value, match.label, match.delta))
    return found


def qutebrowser_replacements(palette: dict, mode: str) -> list[Replacement]:
    """Every stock qutebrowser default the patcher recolours."""
    try:
        defaults = patch_qutebrowser.stock_defaults(patch_qutebrowser.stock_source())
    except OSError:
        return []
    candidates = color_match.build_palette_map(palette)[mode]
    found = []
    for key, value in sorted(defaults.items()):
        for index, entry in enumerate(value if isinstance(value, list) else [value]):
            match = color_match.nearest(
                entry, color_match.filter_candidates(key, candidates)
            )
            if match is None:
                continue
            name = f"{key}[{index}]" if isinstance(value, list) else key
            found.append(Replacement(name, entry, match.label, match.delta))
    return found


#: One row per application whose colours are resolved rather than declared.
SOURCES = {
    "vscode": vscode_replacements,
    "qutebrowser": qutebrowser_replacements,
}


def distribution(replacements: list[Replacement]) -> dict[str, float]:
    """Median, p90, p99 and max of the distances."""
    deltas = sorted(entry.delta for entry in replacements)
    if not deltas:
        return {}
    if len(deltas) < 3:
        return {"median": deltas[len(deltas) // 2], "p90": deltas[-1],
                "p99": deltas[-1], "max": deltas[-1]}
    hundredths = statistics.quantiles(deltas, n=100, method="inclusive")
    return {
        "median": statistics.median(deltas),
        "p90": hundredths[89],
        "p99": hundredths[98],
        "max": deltas[-1],
    }


def _section(app: str, mode: str, replacements: list[Replacement]) -> list[str]:
    stats = distribution(replacements)
    if not stats:
        return [f"#### {app} — `{mode}`", "", "_Nothing to match._"]
    lines = [
        f"#### {app} — `{mode}` ({len(replacements)} colours)",
        "",
        "| median | p90 | p99 | max |",
        "| --- | --- | --- | --- |",
        f"| {stats['median']:.1f} | {stats['p90']:.1f} | {stats['p99']:.1f} "
        f"| {stats['max']:.1f} |",
        "",
        f"Furthest {WORST}:",
        "",
        "| Field | Stock colour | Replaced by | ΔE |",
        "| --- | --- | --- | --- |",
    ]
    furthest = sorted(replacements, key=lambda entry: -entry.delta)[:WORST]
    lines += [
        f"| `{entry.key}` | `{entry.original}` | `{entry.label}` | {entry.delta:.1f} |"
        for entry in furthest
    ]
    return lines


def generate_markdown() -> str:
    """Return the markdown body for the COLOR_DISTANCE block in ``docs/color-distance.md``."""
    palette = _bundle_palette()
    if palette is None:
        return "_No palette in the configured bundle; nothing to measure._"
    setup = read_setup()
    lines = [
        f"Measured against the `{setup['desktop']['theme']}` bundle's palette, in CAM16-UCS. "
        "A ΔE of about 2 is the smallest difference an eye reliably notices; past roughly 20 "
        "the replacement is a different colour rather than a near one.",
    ]
    for app, replacements_for in SOURCES.items():
        for mode in patch_vsc.MODES:
            lines += ["", *_section(app, mode, replacements_for(palette, mode))]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--app", choices=sorted(SOURCES), help="report one application")
    parser.add_argument("--json", action="store_true", help="emit the raw distances")
    arguments = parser.parse_args(argv)

    palette = _bundle_palette()
    if palette is None:
        print("No palette in the configured bundle.", file=sys.stderr)
        return 1
    if not arguments.app and not arguments.json:
        print(generate_markdown())
        return 0

    apps = [arguments.app] if arguments.app else list(SOURCES)
    payload: dict[str, Any] = {}
    for app in apps:
        for mode in patch_vsc.MODES:
            replacements = SOURCES[app](palette, mode)
            if arguments.json:
                payload[f"{app}.{mode}"] = {
                    "distribution": distribution(replacements),
                    "replacements": [entry._asdict() for entry in replacements],
                }
            else:
                print("\n".join(_section(app, mode, replacements)))
                print()
    if arguments.json:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
