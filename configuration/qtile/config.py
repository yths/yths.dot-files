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

import json
import os

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

icons = {
    "monitor": "󰍹 ",
    "group": " "
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
    # Also on startup, so the focused screen is outlined before the pointer first moves.
    hook.subscribe.startup_complete(highlight_focused_screen)

screens = [
    Screen(
        top=bar.Bar(
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
                widget.TaskList(
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
                    padding_y=round(
                        configuration["monitors"][monitor]["scaling_factor"]
                        * configuration["font"]["size"]
                        / 3
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
                widgets.claude_usage.WidgetClaudeUsage(
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
                    r=r,
                    icons={"CC:98:8B:99:F4:E5": "󰋎", "AC:80:0A:A4:66:EB": "󰋎"},
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
