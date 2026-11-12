"""Detect connected monitors via ``screeninfo``.

``get()`` returns a dict keyed by output name (e.g. ``HDMI-0``) with per-monitor geometry,
physical dimensions, derived DPI, diagonal, scaling factor, and ``is_primary`` flag.
Consumed by ``install.py`` to merge into the active theme bundle's ``config.json``.
"""

import contextlib

import screeninfo


def get() -> dict[str, dict]:
    monitors = {}
    for m in screeninfo.get_monitors():
        print(f"Monitor: {m.name}")
        diagonal = (m.width**2 + m.height**2)**0.5
        diagonal_mm = (m.width_mm**2 + m.height_mm**2)**0.5
        print(f"width_dpi = {round(m.width / m.width_mm * 25.4)}")
        print(f"height_dpi = {round(m.height / m.height_mm * 25.4)}")
        print(f"diagonal_dpi = {round(diagonal / diagonal_mm * 25.4)}")
        is_primary = False
        with contextlib.suppress(AttributeError):
            is_primary = m.is_primary
        monitors[m.name] = {
            "width": m.width,
            "width_mm": m.width_mm,
            "width_dpi": round(m.width / m.width_mm * 25.4),
            "height": m.height,
            "height_mm": m.height_mm,
            "height_dpi": round(m.height / m.height_mm * 25.4),
            "diagonal": diagonal,
            "diagonal_mm": diagonal_mm,
            "diagonal_dpi": round(diagonal / diagonal_mm * 25.4),
            "scaling_factor": round(diagonal / diagonal_mm * 25.4) / 100,
            "is_primary": is_primary,
        }

    return monitors

if __name__ == '__main__':
    monitors = get()
