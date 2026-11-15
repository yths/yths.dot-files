"""Convert a theme bundle's legacy ``palette.pkl`` into the ``palette.json`` it now ships.

Bundles carried the palette as a pickle until the format moved to JSON: unpickling a file
another tool dropped into ``assets/`` runs whatever code it was written to run. This reads
the old file through an unpickler that refuses every global, so only builtin containers and
strings can come out of it -- which is all a palette, ``{mode: {token: hex}}``, ever was --
and writes it next to the pickle. The pickle is left in place; delete it once satisfied.

    python helper/convert_palette.py assets/<name> [assets/<other> ...]
"""

import argparse
import io
import json
import pickle
import sys
from pathlib import Path
from typing import Any


class _DataOnlyUnpickler(pickle.Unpickler):
    def find_class(self, module: str, name: str) -> Any:
        raise pickle.UnpicklingError(f"refusing to load {module}.{name}: a palette is plain data")


def load_legacy_palette(data: bytes) -> dict[str, dict[str, str]]:
    """The palette inside ``data``, or ``ValueError`` if it is anything but one."""
    palette = _DataOnlyUnpickler(io.BytesIO(data)).load()
    if not isinstance(palette, dict) or not all(
        isinstance(mode, str)
        and isinstance(tokens, dict)
        and all(isinstance(k, str) and isinstance(v, str) for k, v in tokens.items())
        for mode, tokens in palette.items()
    ):
        raise ValueError("not a {mode: {token: hex}} palette")
    return palette


def convert(bundle: Path) -> Path:
    target = bundle / "palette.json"
    palette = load_legacy_palette((bundle / "palette.pkl").read_bytes())
    target.write_text(json.dumps(palette, indent=4) + "\n", encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("bundles", nargs="+", type=Path, help="bundle directories")
    arguments = parser.parse_args(argv)
    failed = 0
    for bundle in arguments.bundles:
        try:
            print(f"wrote {convert(bundle)}")
        except (OSError, pickle.UnpicklingError, ValueError, EOFError) as error:
            print(f"{bundle}: {error}", file=sys.stderr)
            failed = 1
    return failed


if __name__ == "__main__":
    sys.exit(main())
