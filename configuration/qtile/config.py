# Copyright (c) 2010 Aldo Cortesi
# Copyright (c) 2010, 2014 dequis
# Copyright (c) 2012 Randall Ma
# Copyright (c) 2012-2014 Tycho Andersen
# Copyright (c) 2012 Craig Barnes
# Copyright (c) 2013 horsik
# Copyright (c) 2013 Tao Sauvage
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# The notice above is qtile's, and stays: this file began as their default configuration and
# still contains substantial portions of it, which the MIT licence requires the notice to
# accompany. Everything below the imports is this repository's.

import importlib
import json
import os
import subprocess
import sys

from libqtile import bar, hook, layout, qtile, widget
from libqtile.config import (
    Click,
    Drag,
    DropDown,
    Group,
    Key,
    KeyChord,
    Match,
    ScratchPad,
    Screen,
)
from libqtile.lazy import lazy
from libqtile.log_utils import logger

#: This file's repository, resolved through the ~/.config/qtile symlink qtile loads it
#: through, so the hooks below can reach helper/ without depending on where it was cloned.
REPOSITORY_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
)

# Put helper/ on the path before the widget modules below are imported: several of them read
# the symbol vocabulary, and an import that resolved only under pytest -- whose conftest adds
# the same directory -- would fail at qtile startup and take the bar down with it.
HELPER_DIRECTORY = os.path.join(REPOSITORY_ROOT, "helper")
sys.path.insert(0, HELPER_DIRECTORY)

# A reload re-executes this file and the modules under ~/.config/qtile, and nothing else: a
# helper/ module stays at whatever version qtile *started* with. Once that meant a new
# function in symbols.py did not exist as far as this file was concerned, and every reload
# was refused as a configuration error until a full restart. Reversed, because a module's
# own imports enter sys.modules after it, so dependencies are refreshed before dependants.
for _module in reversed(list(sys.modules.values())):
    _origin = getattr(_module, "__file__", None)
    if _origin and os.path.dirname(os.path.realpath(_origin)) == HELPER_DIRECTORY:
        importlib.reload(_module)

try:
    import redis

    pool = redis.ConnectionPool(
        host=os.environ.get("BACKEND_REDIS_HOST", "localhost"),
        port=int(os.environ.get("BACKEND_REDIS_PORT", "6379")),
        db=int(os.environ.get("BACKEND_REDIS_DB", "1")),
        socket_connect_timeout=0.5,  # connect phase
        socket_timeout=0.5,          # read/write phase
        health_check_interval=30,
        )
    r = redis.Redis(connection_pool=pool)
except ImportError:
    r = None
except redis.exceptions.ConnectionError:
    r = None

import shared.hover_bar
import shared.idle_guard
import shared.monitors
import shared.session
import shared.task_list
import symbols as vocabulary
import widgets.audio
import widgets.bluetooth
import widgets.broadcast
import widgets.claude_usage
import widgets.location
import widgets.power_supply
import widgets.service_state
import widgets.updates
import widgets.vpn

try:
    with open(os.path.expanduser("~/.config/config.json"), encoding="utf-8") as handle:
        configuration = json.load(handle)
except FileNotFoundError:
    configuration = {
        "font_size": 10,
    }

theme = configuration["state"]["theme"]

# Outline the screen that currently has focus. Set the width to 0 to switch the whole
# feature off: no extra bars are constructed, the top bar keeps its original geometry, and
# the hooks below are never registered.
FOCUS_BORDER_WIDTH = 3
FOCUS_BORDER_ACTIVE = configuration["palette"][theme]["highlight"]
FOCUS_BORDER_INACTIVE = configuration["palette"][theme]["background"]

mod = "mod4"
terminal = "kitty"  # guess_terminal()

# The symbols every cell below draws, resolved the way its colours already are: from
# ~/.config/config.json, which the installer wrote by merging the active bundle's overrides
# over the ASCII vocabulary in helper/symbols.py. Reached through REPOSITORY_ROOT rather than
# imported outright, the same way the hooks below reach helper/ -- and *resolved* rather than
# read straight out of the dict, so a configuration file written before the vocabulary
# existed still brings the bar up in ASCII instead of raising KeyError in every cell.
SYMBOLS, STRINGS = vocabulary.resolve(configuration)

# Trailing space because the ink of a nerd-font glyph overruns its advance width; an ASCII
# fallback does not need it but is not harmed by it.
icons = {
    "monitor": f"{SYMBOLS['bar.monitor']} ",
    "group": f"{SYMBOLS['bar.group']} ",
}

keys = [
    # A list of available commands that can be bound to keys can be found
    # at https://docs.qtile.org/en/latest/manual/config/lazy.html
    # Switch between windows
    Key([mod], "h", lazy.layout.left(), desc="Move focus to left"),
    Key([mod], "l", lazy.layout.right(), desc="Move focus to right"),
    Key([mod], "j", lazy.layout.down(), desc="Move focus down"),
    Key([mod], "k", lazy.layout.up(), desc="Move focus up"),
    Key([mod], "space", lazy.layout.next(), desc="Move window focus to other window"),
    # Move windows between left/right columns or move up/down in current stack.
    # Moving out of range in Columns layout will create new column.
    Key(
        [mod, "shift"], "h", lazy.layout.shuffle_left(), desc="Move window to the left"
    ),
    Key(
        [mod, "shift"],
        "l",
        lazy.layout.shuffle_right(),
        desc="Move window to the right",
    ),
    Key([mod, "shift"], "j", lazy.layout.shuffle_down(), desc="Move window down"),
    Key([mod, "shift"], "k", lazy.layout.shuffle_up(), desc="Move window up"),
    # Grow windows. If current window is on the edge of screen and direction
    # will be to screen edge - window would shrink.
    Key([mod, "control"], "h", lazy.layout.grow_left(), desc="Grow window to the left"),
    Key(
        [mod, "control"], "l", lazy.layout.grow_right(), desc="Grow window to the right"
    ),
    Key([mod, "control"], "j", lazy.layout.grow_down(), desc="Grow window down"),
    Key([mod, "control"], "k", lazy.layout.grow_up(), desc="Grow window up"),
    Key([mod], "n", lazy.layout.normalize(), desc="Reset all window sizes"),
    # Toggle between split and unsplit sides of stack.
    # Split = all windows displayed
    # Unsplit = 1 window displayed, like Max layout, but still with
    # multiple stack panes
    Key(
        [mod, "shift"],
        "Return",
        lazy.layout.toggle_split(),
        desc="Toggle between split and unsplit sides of stack",
    ),
    Key([mod], "Return", lazy.spawn(terminal), desc="Launch terminal"),
    # Toggle between different layouts as defined below
    Key([mod], "Tab", lazy.next_layout(), desc="Toggle between layouts"),
    Key([mod], "w", lazy.window.kill(), desc="Kill focused window"),
    Key(
        [mod, "control"],
        "f",
        lazy.window.toggle_fullscreen(),
        desc="Toggle fullscreen on the focused window",
    ),
    Key(
        [mod],
        "t",
        lazy.window.toggle_floating(),
        desc="Toggle floating on the focused window",
    ),
    Key([mod, "control"], "r", lazy.restart(), desc="Reload the config"),
    Key([mod, "control"], "q", lazy.shutdown(), desc="Shutdown Qtile"),
    Key([mod], "r", lazy.spawn("rofi -show run"), desc="Spawn a command using rofi"),
    Key(
        [mod, "shift"],
        "r",
        lazy.spawn("rofi -show window"),
        desc="Switch to any window via rofi (entries prefixed with their group number).",
    ),
    # Through the launcher rather than xsecurelock directly: the launcher sources the
    # colours helper/patch_lock.py generates, so the lock screen follows the theme. Spawning
    # xsecurelock bare gave a black screen with a white prompt whatever the palette said.
    Key(
        [mod], "Home",
        lazy.spawn(os.path.expanduser("~/.config/lock/lock.sh")),
        desc="Lock the screen",
    ),
    # The dedicated key, where a keyboard has one. It cannot collide with anything.
    Key(
        [], "XF86ScreenSaver",
        lazy.spawn(os.path.expanduser("~/.config/lock/lock.sh")),
        desc="Lock the screen",
    ),
    Key(
        [],
        "XF86AudioMute",
        lazy.spawn("pactl set-sink-mute @DEFAULT_SINK@ toggle"),
        desc="Toggle mute",
    ),
    Key(
        [],
        "XF86AudioLowerVolume",
        lazy.spawn("pactl set-sink-volume @DEFAULT_SINK@ -5%"),
        desc="Lower volume",
    ),
    Key(
        [],
        "XF86AudioRaiseVolume",
        lazy.spawn("pactl set-sink-volume @DEFAULT_SINK@ +5%"),
        desc="Raise volume",
    ),
    Key(
        [],
        "F1",
        lazy.group["kitty"].dropdown_toggle("vim"),
        desc="Toggle vim scratchpad",
    ),
    Key(
        [],
        "F2",
        lazy.group["kitty"].dropdown_toggle("pulsemixer"),
        desc="Toggle pulsemixer scratchpad",
    ),
]

# Add key bindings to switch VTs in Wayland.
# We can't check qtile.core.name in default config as it is loaded before qtile is started
# We therefore defer the check until the key binding is run by using .when(func=...)
for vt in range(1, 8):
    keys.append(
        Key(
            ["control", "mod1"],
            f"f{vt}",
            lazy.core.change_vt(vt).when(func=lambda: qtile.core.name == "wayland"),
            desc=f"Switch to VT{vt}",
        )
    )

subscript_characters = ["<sub>j</sub>", "<sub>k</sub>", "<sub>l</sub>", "<sub>;</sub>"]
characters = ["j", "k", "l", "semicolon"]
groups = []
for m, _ in enumerate(configuration["monitors"]):
    groups += [
        Group(
            str(i),
            label=f"{icons['group']}{subscript_characters[(i - 1) % len(subscript_characters)]}",
        )
        for i in range(
            1 + m * len(subscript_characters),
            len(subscript_characters) + 1 + m * len(subscript_characters),
        )
    ]


groups += [
    ScratchPad(
        "kitty",
        [
            DropDown(
                "vim",
                f"{terminal} -e vim",
                width=0.8,
                height=0.8,
                x=0.1,
                y=0.1,
                on_focus_lost_hide=True,
                warp_pointer=False,
            ),
            DropDown(
                "pulsemixer",
                f"{terminal} -e pulsemixer",
                width=0.8,
                height=0.8,
                x=0.1,
                y=0.1,
                on_focus_lost_hide=True,
                warp_pointer=False,
            ),
        ],
    ),
]


#: A hotplug raises several screen-change events in quick succession as outputs settle, and
#: each reload tears the bar down and builds it again. Coalescing them into one reload is the
#: difference between a flicker and a stutter.
SCREEN_SETTLE_SECONDS = 1.0


class _ScreenChange:
    """Whether a reload is already scheduled.

    An attribute rather than a module global so the handler can set it without rebinding a
    name it does not own -- which is the thing that makes module state hard to follow.
    """

    pending = False


@hook.subscribe.screen_change
def handle_screen_change(event: object) -> None:
    """Re-read the monitors when one is plugged in or unplugged.

    Every size here is derived from monitor geometry, and that geometry was read once by
    install.py -- so without this a new display got the old display's scaling factor until
    somebody restarted qtile.
    """
    if _ScreenChange.pending:
        return
    _ScreenChange.pending = True
    qtile.call_later(SCREEN_SETTLE_SECONDS, apply_screen_change)


def apply_screen_change() -> None:
    """Record the new layout and rebuild against it, if anything actually changed."""
    _ScreenChange.pending = False

    if not shared.monitors.refresh():
        # The event fires for changes that are not a plug or an unplug. Reloading anyway
        # would drop the bar every time a resolution was queried.
        return

    # Rewrite the configurations that scale to the display -- the X server's DPI, rofi's
    # width, dunst's offset -- without reloading the running programs: this function restarts
    # qtile a line later, and letting the patcher do it too would restart it twice.
    subprocess.Popen(
        args=[
            "python",
            os.path.join(REPOSITORY_ROOT, "helper", "patch_configurations.py"),
            "--no-reload",
        ]
    )
    logger.warning("Monitor layout changed; reloading the configuration.")
    qtile.reload_config()


@hook.subscribe.startup
def relabel_groups() -> None:
    """Put back the labels this file gave the groups, over the ones a restart restored.

    ``lazy.restart()`` pickles every group's label and the new process applies them on top of
    the freshly loaded configuration, so a theme switch -- which restarts qtile to pick up the
    new ``bar.group`` glyph -- kept drawing the previous theme's glyph in the group boxes
    until the next login. A config reload restores them the same way. ``startup`` rather
    than ``startup_complete`` because only it fires on a reload, and it fires after the
    restore on all three paths.
    """
    for group in groups:
        if group.name in qtile.groups_map and qtile.groups_map[group.name].label != group.label:
            qtile.groups_map[group.name].set_label(group.label)


@hook.subscribe.startup_complete
def start_session_programs() -> None:
    """Start the programs that could not start before qtile did; see ``shared.session``."""
    for name in shared.session.start_programs():
        logger.info(f"Started {name}.")


class _IdleGuard:
    """State for the idle guard, in a class for the reason ``_ScreenChange`` is.

    ``timeout`` is read once, at startup, rather than written down again here: ~/.xinitrc
    has already set it by then, so this is the value this machine was configured with and
    there is no second copy of it to drift.
    """

    timeout: int | None = None
    running = False


@hook.subscribe.startup_complete
def start_idle_guard() -> None:
    """Begin watching the X idle counter; see ``shared.idle_guard`` for why it needs one."""
    if _IdleGuard.running:
        return
    _IdleGuard.running = True
    _IdleGuard.timeout = shared.idle_guard.screensaver_timeout()
    if not _IdleGuard.timeout:
        logger.warning(
            "The X screen saver timeout is 0 at startup: this session will not lock itself. "
            "Set it in ~/.xinitrc with `xset s <seconds>`."
        )
    qtile.call_later(shared.idle_guard.CHECK_SECONDS, run_idle_guard)


def run_idle_guard() -> None:
    """Reset the idle counter while anything is inhibiting, then look again later."""
    restored, inhibitors = shared.idle_guard.guard(_IdleGuard.timeout)
    if restored:
        logger.warning(
            f"The X screen saver timeout had been set to 0; restored it to "
            f"{_IdleGuard.timeout}s. Something disabled this session's automatic lock."
        )
    if inhibitors:
        logger.info(f"Holding the screen awake for: {', '.join(w for w, _ in inhibitors)}.")
    qtile.call_later(shared.idle_guard.CHECK_SECONDS, run_idle_guard)


@hook.subscribe.startup_complete
def send_to_screens() -> None:
    for m, _ in enumerate(configuration["monitors"]):
        for i in range(
            1 + m * len(subscript_characters),
            len(subscript_characters) + m * len(subscript_characters) + 1,
        ):
            qtile.groups_map[str(i)].toscreen(m)
        qtile.groups_map[str(1 + m * len(subscript_characters))].toscreen(m)


group_chords = []
group_chords_move = []
for m, monitor in enumerate(configuration["monitors"]):
    tmp = []
    tmp_move = []
    for i in range(
        1 + m * len(subscript_characters),
        len(subscript_characters) + 1 + m * len(subscript_characters),
    ):
        tmp.append(
            Key(
                [],
                characters[(i - 1) % len(subscript_characters)],
                lazy.group[str(i)].toscreen(m),
                desc=f"Switch to group {monitor} {i}",
            )
        )
        tmp_move.append(
            Key(
                [],
                characters[(i - 1) % len(subscript_characters)],
                lazy.window.togroup(str(i), switch_group=False),
                desc=f"Switch to and move focused window to group {monitor} {i}",
            )
        )
    group_chords.append(
        KeyChord([], characters[m], tmp, name=f"Switch group on screen {monitor}")
    )
    group_chords_move.append(
        KeyChord(
            [],
            characters[m],
            tmp_move,
            name=f"Switch group on screen {monitor} and move focused window",
        )
    )

tmp_focus = []
for m, monitor in enumerate(configuration["monitors"]):
    tmp_focus.append(
        Key(
            [],
            characters[m],
            lazy.to_screen(m),
            desc=f"Switch to screen {monitor} using subscript characters",
        )
    )
keys.extend(
    [
        KeyChord(
            [mod],
            "s",
            tmp_focus,
            name="Switch focus to screen",
            desc="Switch focus to screen using subscript characters",
        )
    ]
)


keys.extend(
    [
        KeyChord(
            [mod],
            "f",
            group_chords,
            name="Switch to group",
            desc="Switch to group using subscript characters",
        )
    ]
)

keys.extend(
    [
        KeyChord(
            [mod],
            "d",
            group_chords_move,
            name="Move to group",
            desc="Move to group using subscript characters",
        )
    ]
)

# `layouts` and `widget_defaults` are module-level, so they cannot vary per screen: they
# need one monitor's scaling factor, chosen deliberately. Name the primary monitor, which is
# the one `screens` puts first. Indexing with a loop variable left over from the loops above
# reads as if it were per-screen and is not — it picks whichever monitor sorted last.
primary_monitor = next(
    (name for name in configuration["monitors"] if configuration["monitors"][name]["is_primary"]),
    next(iter(configuration["monitors"]), None),
)
primary_scaling_factor = (
    configuration["monitors"][primary_monitor]["scaling_factor"] if primary_monitor else 1.0
)

layouts = [
    layout.Columns(
        border_normal=configuration["palette"][theme]["neutral"],
        border_normal_stack=configuration["palette"][theme]["foreground"],
        border_focus=configuration["palette"][theme]["neutral"],
        border_focus_stack=configuration["palette"][theme]["foreground"],
        border_width=0,
        margin=[
            round(primary_scaling_factor * 10),
            round(primary_scaling_factor * 9.2),
            round(primary_scaling_factor * 20),
            round(primary_scaling_factor * 9.2),
        ],
        margin_on_single=[
            round(primary_scaling_factor * 10),
            round(primary_scaling_factor * 9.2),
            round(primary_scaling_factor * 20),
            round(primary_scaling_factor * 9.2),
        ],
        border_on_single=True,
        initial_ratio=16 / 9,
    ),
    layout.Max(
        border_normal=configuration["palette"][theme]["neutral"],
        border_focus=configuration["palette"][theme]["foreground"],
        border_width=0,
        margin=[
            round(primary_scaling_factor * 10),
            round(primary_scaling_factor * 9.2),
            round(primary_scaling_factor * 20),
            round(primary_scaling_factor * 9.2),
        ],
    ),
]

widget_defaults = {
    "foreground": configuration["palette"][theme]["foreground"],
    "font": configuration["font"]["family"],
    "padding": round(primary_scaling_factor * configuration["font"]["size"] / 4),
}
extension_defaults = widget_defaults.copy()

# Fall back to the plain theme wallpaper rather than leaving `wallpaper` unbound: an
# unexpected `condition` value would otherwise raise NameError below and take the whole
# configuration down, which qtile answers by loading its own default.
wallpaper_key = configuration["state"]["theme"]
if configuration["state"].get("condition") == "urgent":
    wallpaper_key = f"{wallpaper_key}-highlight"
wallpaper = configuration["wallpapers"].get(
    wallpaper_key, configuration["wallpapers"][configuration["state"]["theme"]]
)


def focus_border_size(monitor: str) -> int:
    """Outline thickness for one monitor, scaled like every other measurement here."""
    scaled = round(configuration["monitors"][monitor]["scaling_factor"] * FOCUS_BORDER_WIDTH)
    return max(scaled, 1)


def focus_border_bar(monitor: str) -> bar.Bar:
    """One edge of the focused-screen outline.

    The Spacer is load-bearing, not decoration. ``Bar.draw()`` returns early when a bar has
    no widgets, so a widget-less bar could never repaint when focus moves between monitors.
    The Spacer also fills the bar using ``self.background or self.bar.background``, which is
    what actually applies the colour set by ``highlight_focused_screen`` below.
    """
    return bar.Bar(
        [widget.Spacer()],
        size=focus_border_size(monitor),
        background=FOCUS_BORDER_INACTIVE,
    )


def highlight_focused_screen() -> None:
    """Recolour every screen's outline so only the focused one is accented."""
    for screen in qtile.screens:
        colour = (
            FOCUS_BORDER_ACTIVE if screen is qtile.current_screen else FOCUS_BORDER_INACTIVE
        )
        # The top edge is the main bar's own border; the other three are dedicated bars.
        if screen.top is not None:
            screen.top.border_color = [colour] * 4
            screen.top.draw()
        for edge in (screen.bottom, screen.left, screen.right):
            if edge is not None:
                edge.background = colour
                edge.draw()


if FOCUS_BORDER_WIDTH:
    hook.subscribe.current_screen_change(highlight_focused_screen)
    # Also on every load -- startup, restart and a config reload alike -- so the focused
    # screen is outlined before the pointer first moves. startup_complete fires only on the
    # first two: a reload rebuilt the bars with every edge inactive and left them so, which
    # outlined no screen at all until focus next changed.
    hook.subscribe.startup(highlight_focused_screen)

screens = [
    Screen(
        top=shared.hover_bar.HoverBar(
            [
                widget.TextBox(
                    f"{icons['monitor']}{subscript_characters[m]}",
                    fontsize=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    ),
                ),
                widget.Spacer(
                    length=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    )
                ),
                widgets.broadcast.WidgetBroadcast(
                    symbols=SYMBOLS,
                    r=r,
                    notification_color=configuration["palette"][theme]["notification"],
                    warning_color=configuration["palette"][theme]["warning"],
                    fontsize=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    ),
                    update_interval=1,
                ),
                widget.Spacer(
                    length=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    )
                ),
                widget.GroupBox(
                    highlight_method="text",
                    urgent_alert_method="text",
                    hide_unused=False,
                    markup=True,
                    fontsize=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    ),
                    visible_groups=list(
                        map(
                            str,
                            range(
                                1 + m * len(subscript_characters),
                                len(subscript_characters)
                                + 1
                                + m * len(subscript_characters),
                            ),
                        )
                    ),
                    active=configuration["palette"][theme]["foreground"],
                    inactive=configuration["palette"][theme]["neutral"],
                    this_current_screen_border=configuration["palette"][theme][
                        "highlight"
                    ],
                    urgent_text=configuration["palette"][theme]["notification"],
                    urgent_border=configuration["palette"][theme]["notification"],
                ),
                widget.Spacer(
                    length=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    )
                ),
                widget.Prompt(
                    fontsize=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    )
                ),
                shared.task_list.CentredTaskList(
                    icon_size=0,
                    highlight_method="block",
                    borderwidth=0,
                    border=configuration["palette"][theme]["highlight"],
                    urgent_border=configuration["palette"][theme]["notification"],
                    markup_focused="<span foreground='"
                    + configuration["palette"][theme]["background"]
                    + "'>{}</span>",
                    foreground=configuration["palette"][theme]["neutral"],
                    fontsize=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    ),
                    padding_x=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    ),
                ),
                widget.Chord(
                    chords_colors={
                        "launch": (
                            configuration["palette"][theme]["highlight"],
                            configuration["palette"][theme]["foreground"],
                        ),
                    },
                    name_transform=lambda name: name.upper(),
                    fontsize=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    ),
                ),
                # StatusNotifier, not Systray. The two are different protocols: Systray is
                # XEmbed, where the application docks its own X window in the bar, and
                # StatusNotifier is the freedesktop D-Bus specification. inhibit-bridge
                # publishes org.kde.StatusNotifierItem and needs a host to register with --
                # with only a Systray in the bar it logged "systray error: failed to
                # register: The name is not activatable" and showed nothing.
                #
                # On every bar, unlike Systray, which qtile allows only once: the host behind
                # this widget is a module-level singleton that every instance shares, so the
                # tray is reachable from whichever monitor is in front of you.
                widget.StatusNotifier(
                    icon_size=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    ),
                    padding=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                        * 0.5
                    ),
                ),
                widget.Spacer(
                    length=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    )
                ),
                widgets.claude_usage.WidgetClaudeUsage(
                    symbols=SYMBOLS,
                    r=r,
                    warning_color=configuration["palette"][theme]["warning"],
                    notification_color=configuration["palette"][theme]["notification"],
                    fontsize=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    ),
                    update_interval=5,
                ),
                widget.Spacer(
                    length=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    )
                ),
                widgets.audio.WidgetAudio(
                    symbols=SYMBOLS,
                    r=r,
                    notification_color=configuration["palette"][theme]["notification"],
                    fontsize=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    ),
                    update_interval=0.1,
                ),
                widget.Spacer(
                    length=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    )
                ),
                widgets.bluetooth.WidgetBluetooth(
                    symbols=SYMBOLS,
                    r=r,
                    devices=vocabulary.bluetooth_devices(configuration, SYMBOLS),
                    warning_color=configuration["palette"][theme]["warning"],
                    fontsize=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    ),
                    update_interval=1,
                ),
                widget.Spacer(
                    length=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    )
                ),
                widgets.updates.WidgetUpdates(
                    symbols=SYMBOLS,
                    r=r,
                    notification_color=configuration["palette"][theme]["highlight"],
                    warning_color=configuration["palette"][theme]["notification"],
                    fontsize=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    ),
                    update_interval=1,
                ),
                widget.Spacer(
                    length=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    )
                ),
                widgets.power_supply.WidgetPowerSupply(
                    symbols=SYMBOLS,
                    r=r,
                    warning_color=configuration["palette"][theme]["warning"],
                    fontsize=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    ),
                    update_interval=1,
                ),
                widget.Spacer(
                    length=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    )
                ),
                widgets.location.WidgetLocation(
                    symbols=SYMBOLS,
                    r=r,
                    notification_color=configuration["palette"][theme]["highlight"],
                    fontsize=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    ),
                    update_interval=1,
                ),
                widget.Spacer(
                    length=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    )
                ),
                widgets.vpn.WidgetVPN(
                    symbols=SYMBOLS,
                    r=r,
                    warning_color=configuration["palette"][theme]["warning"],
                    fontsize=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    ),
                    update_interval=1,
                ),
                widget.Spacer(
                    length=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    )
                ),
                widget.Clock(
                    format="%Y-%m-%d %a %H:%M:%S",
                    fontsize=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    ),
                ),
                widget.Chord(
                    fontsize=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    )
                ),
                widgets.service_state.WidgetServiceState(
                    symbols=SYMBOLS,
                    service="backend.service",
                    warning_color=configuration["palette"][theme]["warning"],
                    fontsize=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                    ),
                    update_interval=1,
                ),
            ],
            size=round(
                configuration["monitors"][monitor]["scaling_factor"]
                * configuration["font"]["size"]
                * 2.75
            ),
            margin=[0, 0, 0, 0],
            background=configuration["palette"][theme]["background"],
            # North, east and west only: the south edge of the bar is interior to the
            # screen, so it never forms part of the outline.
            border_width=(
                [focus_border_size(monitor), focus_border_size(monitor), 0, focus_border_size(monitor)]
                if FOCUS_BORDER_WIDTH
                else 0
            ),
            border_color=FOCUS_BORDER_INACTIVE,
        ),
        bottom=focus_border_bar(monitor) if FOCUS_BORDER_WIDTH else None,
        left=focus_border_bar(monitor) if FOCUS_BORDER_WIDTH else None,
        right=focus_border_bar(monitor) if FOCUS_BORDER_WIDTH else None,
        background=configuration["palette"][theme]["background"],
        wallpaper=wallpaper,
        wallpaper_mode="fill",
        # If dragging or resizing floating windows feels laggy on X11, capping the event
        # rate helps: set x11_drag_polling_rate to e.g. 60. Uncapped by default.
    )
    for m, monitor in enumerate(
        sorted(
            configuration["monitors"],
            key=lambda x: configuration["monitors"][x]["is_primary"],
            reverse=True,
        )
    )
]

# Drag floating layouts.
mouse = [
    Drag(
        [mod],
        "Button1",
        lazy.window.set_position_floating(),
        start=lazy.window.get_position(),
    ),
    Drag(
        [mod], "Button3", lazy.window.set_size_floating(), start=lazy.window.get_size()
    ),
    Click([mod], "Button2", lazy.window.bring_to_front()),
]

dgroups_key_binder = None
dgroups_app_rules = []  # type: list
follow_mouse_focus = True
bring_front_click = False
floats_kept_above = True
cursor_warp = True
floating_layout = layout.Floating(
    float_rules=[
        # Run the utility of `xprop` to see the wm class and name of an X client.
        *layout.Floating.default_float_rules,
        Match(wm_class="confirmreset"),  # gitk
        Match(wm_class="makebranch"),  # gitk
        Match(wm_class="maketag"),  # gitk
        Match(wm_class="ssh-askpass"),  # ssh-askpass
        Match(title="branchdialog"),  # gitk
        Match(title="pinentry"),  # GPG key password entry
    ],
    border_focus=configuration["palette"][theme]["highlight"],
    border_normal=configuration["palette"][theme]["background"],
    border_width=2,
)
auto_fullscreen = True
focus_on_window_activation = "smart"
reconfigure_screens = True

# If things like steam games want to auto-minimize themselves when losing
# focus, should we respect this or not?
auto_minimize = True

# When using the Wayland backend, this can be used to configure input devices.
wl_input_rules = None

# xcursor theme (string or None) and size (integer) for Wayland backend
wl_xcursor_theme = None
wl_xcursor_size = 24

# A deliberate lie, inherited from qtile's default configuration. Only java UI toolkits read
# this string, and they misbehave under a window manager they do not recognise; LG3D is on
# their whitelist. Change it only if a java application is misrendering.
wmname = "LG3D"
