"""`helper/convert_palette.py`: the one place a legacy ``palette.pkl`` is still read.

Bundles moved to ``palette.json`` because unpickling a file another tool dropped into
``assets/`` runs whatever it was written to run. The converter exists for bundles exported
before that, and it must not reopen the hole it is there to close.
"""

import json
import os
import pickle
from pathlib import Path

import convert_palette
import pytest

PALETTE = {"dark": {"background": "#000000"}, "light": {"background": "#ffffff"}}


class _Payload:
    def __reduce__(self) -> tuple:
        return (os.system, ("true",))


def test_a_palette_round_trips_to_json(tmp_path: Path) -> None:
    (tmp_path / "palette.pkl").write_bytes(pickle.dumps(PALETTE))
    assert convert_palette.main([str(tmp_path)]) == 0
    assert json.loads((tmp_path / "palette.json").read_text()) == PALETTE


def test_a_pickle_that_calls_anything_is_refused() -> None:
    with pytest.raises(pickle.UnpicklingError):
        convert_palette.load_legacy_palette(pickle.dumps(_Payload()))


def test_a_pickle_that_is_not_a_palette_is_refused() -> None:
    with pytest.raises(ValueError, match="palette"):
        convert_palette.load_legacy_palette(pickle.dumps({"dark": ["#000000"]}))


def test_no_bundle_reads_a_pickle_any_more() -> None:
    root = Path(__file__).resolve().parent.parent
    assert (root / "assets" / "default" / "palette.json").is_file()
    assert not (root / "assets" / "default" / "palette.pkl").exists()
