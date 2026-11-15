"""qutebrowser configuration: the hand-written half.

Only what this repository changes lives here. ``template_config.py`` beside it is the stock
dump ``qutebrowser --config-py`` writes, and is the reference for every setting's name,
type and default -- look a setting up there, not here.

Every colour is set in ``~/.config/qutebrowser/theme.py``, which ``helper/patch_qutebrowser.py``
writes on each theme switch by replacing each stock default with the nearest colour in the
active palette. Run ``python helper/patch_qutebrowser.py`` to regenerate it,
``--report-unmapped`` to see the settings it deliberately leaves stock, and see
docs/color-distance.md for how near "nearest" got. Setting a ``c.colors.*`` here would override
the theme. Sourced rather than inlined so this file keeps what a generated file cannot carry:
the monitor-scaled tab padding, the dark-mode switch and the bindings.
"""

import json
import os

with open(os.path.expanduser("~/.config/config.json"), encoding="utf-8") as input_handle:
    configuration = json.load(input_handle)

# Injected by qutebrowser when it runs this file; restated so linters see them defined.
c = c  # noqa: F821, PLW0127
config = config  # noqa: F821, PLW0127

# Settings made through the GUI still load.
config.load_autoconfig(True)

# Guarded because a clone that has not been patched yet has no theme.py.
if os.path.exists(os.path.expanduser("~/.config/qutebrowser/theme.py")):
    config.source("theme.py")

# ------------------------------------------------------------------------------- fonts

c.fonts.default_family = [configuration["font"]["family"]]
c.fonts.default_size = str(configuration["font"]["size"]) + "px"
c.fonts.contextmenu = configuration["font"]["family"]

# ----------------------------------------------------------------------------- general

c.auto_save.session = True
c.backend = "webengine"
c.changelog_after_upgrade = "never"

# ------------------------------------------------------------------------------- pages

# Follows the desktop's light/dark state; `td` toggles it for the session.
dark = configuration["state"]["theme"] == "dark"
c.colors.webpage.darkmode.enabled = dark
config.bind("td", "config-cycle colors.webpage.darkmode.enabled true false")

config.set("content.autoplay", False)
config.set("content.media.video_capture", True)
config.set("content.media.audio_capture", True)

# -------------------------------------------------------------------------------- tabs

c.tabs.favicons.show = "never"
c.tabs.focus_stack_size = -1

# A third of the scaled font size, averaged across monitors. With no monitors recorded --
# installed without a display, or before detection ran -- the font size is used unscaled:
# dividing by the empty list raised ZeroDivisionError, and qutebrowser started on defaults.
padding_sizes = [
    round(monitor["scaling_factor"] * configuration["font"]["size"])
    for monitor in configuration.get("monitors", {}).values()
]
padding_size = (
    sum(padding_sizes) // len(padding_sizes) if padding_sizes else configuration["font"]["size"]
) // 3
c.tabs.padding = {
    "top": padding_size,
    "bottom": padding_size,
    "left": padding_size,
    "right": padding_size,
}

# ---------------------------------------------------------------------------- bindings

config.bind(",M", "hint links spawn mpv {hint-url}")
config.bind(",m", "hint links spawn mpv --fs {hint-url}")
