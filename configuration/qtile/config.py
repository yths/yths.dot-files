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

import json
import os

from libqtile import bar, hook, layout, qtile, widget
from libqtile.config import (
    Click,
    Drag,
    Group,
    ScratchPad,
    DropDown,
    Key,
    KeyChord,
    Match,
    Screen,
)
from libqtile.lazy import lazy
# from libqtile.utils import guess_terminal

try:
    import redis

    pool = redis.ConnectionPool(
        host=os.environ.get("NBS_REDIS_HOST", "localhost"),
        port=int(os.environ.get("NBS_REDIS_PORT", 6379)),
        db=int(os.environ.get("NBS_REDIS_DB", 1)),
        socket_connect_timeout=0.5,  # connect phase
        socket_timeout=0.5,          # read/write phase
        health_check_interval=30,  
        )
    r = redis.Redis(connection_pool=pool)
except ImportError:
    r = None
except redis.exceptions.ConnectionError:
    r = None

import widgets.bluetooth
import widgets.location
import widgets.power_supply
import widgets.service_state
import widgets.updates
import widgets.audio
import widgets.stream_state
import widgets.vpn

try:
    configuration = json.load(open(os.path.expanduser("~/.config/config.json")))
except FileNotFoundError:
    configuration = {
        "font_size": 10,
    }

theme = configuration["state"]["theme"]

mod = "mod4"
terminal = "kitty"  # guess_terminal()

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
    Key([mod], "Home", lazy.spawn("xsecurelock"), desc="Lock the screen"),
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
            label=f"⏺{subscript_characters[(i - 1) % len(subscript_characters)]}",
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
def send_to_screens():
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

layouts = [
    layout.Columns(
        border_normal=configuration["palette"][theme]["neutral"],
        border_normal_stack=configuration["palette"][theme]["foreground"],
        border_focus=configuration["palette"][theme]["neutral"],
        border_focus_stack=configuration["palette"][theme]["foreground"],
        border_width=0,
        margin=[
            int(round(configuration["monitors"][monitor]["scaling_factor"] * 10)),
            int(round(configuration["monitors"][monitor]["scaling_factor"] * 9.2)),
            int(round(configuration["monitors"][monitor]["scaling_factor"] * 20)),
            int(round(configuration["monitors"][monitor]["scaling_factor"] * 9.2)),
        ],
        margin_on_single=[
            int(round(configuration["monitors"][monitor]["scaling_factor"] * 10)),
            int(round(configuration["monitors"][monitor]["scaling_factor"] * 9.2)),
            int(round(configuration["monitors"][monitor]["scaling_factor"] * 20)),
            int(round(configuration["monitors"][monitor]["scaling_factor"] * 9.2)),
        ],
        border_on_single=True,
        initial_ratio=16 / 9,
    ),
    layout.Max(
        border_normal=configuration["palette"][theme]["neutral"],
        border_focus=configuration["palette"][theme]["foreground"],
        border_width=0,
        margin=[
            int(round(configuration["monitors"][monitor]["scaling_factor"] * 10)),
            int(round(configuration["monitors"][monitor]["scaling_factor"] * 9.2)),
            int(round(configuration["monitors"][monitor]["scaling_factor"] * 20)),
            int(round(configuration["monitors"][monitor]["scaling_factor"] * 9.2)),
        ],
    ),
]

widget_defaults = dict(
    foreground=configuration["palette"][theme]["foreground"],
    font=configuration["font"]["family"],
    padding=int(
        round(
            configuration["monitors"][monitor]["scaling_factor"]
            * configuration["font"]["size"]
            / 4
        )
    ),
)
extension_defaults = widget_defaults.copy()

if configuration["state"]["theme"] == "light":
    if configuration["state"]["condition"] == "normal":
        wallpaper = configuration["wallpapers"]["light"]
    elif configuration["state"]["condition"] == "urgent":
        wallpaper = configuration["wallpapers"]["light-highlight"]
else:
    if configuration["state"]["condition"] == "normal":
        wallpaper = configuration["wallpapers"]["dark"]
    elif configuration["state"]["condition"] == "urgent":
        wallpaper = configuration["wallpapers"]["dark-highlight"]
screens = [
    Screen(
        top=bar.Bar(
            [
                widget.TextBox(
                    f"󰍹 {subscript_characters[m]}",
                    fontsize=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
                    ),
                ),
                widget.Spacer(
                    length=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
                    )
                ),
                widgets.stream_state.WidgetStreamState(
                    r=r,
                    notification_color=configuration["palette"][theme]["notification"],
                    warning_color=configuration["palette"][theme]["warning"],
                    fontsize=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
                    ),
                    update_interval=1,
                ),
                widget.Spacer(
                    length=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
                    )
                ),
                widget.GroupBox(
                    highlight_method="text",
                    urgent_alert_method="text",
                    hide_unused=False,
                    markup=True,
                    fontsize=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
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
                    # highlight_color="#999900",
                    this_current_screen_border=configuration["palette"][theme][
                        "highlight"
                    ],
                    # this_screen_border="#ff00ff",
                    # other_current_screen_border="#990000",
                    # other_screen_border="#000099",
                    urgent_text=configuration["palette"][theme]["notification"],
                    urgent_border=configuration["palette"][theme]["notification"],
                ),
                widget.Spacer(
                    length=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
                    )
                ),
                widget.Prompt(
                    fontsize=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
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
                    fontsize=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
                    ),
                    padding_x=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
                    ),
                    padding_y=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                            / 3
                        )
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
                    fontsize=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
                    ),
                ),
                widgets.audio.WidgetAudio(
                    r=r,
                    notification_color=configuration["palette"][theme]["notification"],
                    fontsize=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
                    ),
                    update_interval=0.1,
                ),
                widget.Spacer(
                    length=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
                    )
                ),
                widgets.bluetooth.WidgetBluetooth(
                    r=r,
                    icons={"CC:98:8B:99:F4:E5": "󰋎", "AC:80:0A:A4:66:EB": "󰋎"},
                    warning_color=configuration["palette"][theme]["warning"],
                    fontsize=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
                    ),
                    update_interval=1,
                ),
                widget.Spacer(
                    length=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
                    )
                ),
                widgets.updates.WidgetUpdates(
                    r=r,
                    notification_color=configuration["palette"][theme]["highlight"],
                    warning_color=configuration["palette"][theme]["notification"],
                    fontsize=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
                    ),
                    update_interval=1,
                ),
                widget.Spacer(
                    length=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
                    )
                ),
                widgets.power_supply.WidgetPowerSupply(
                    r=r,
                    warning_color=configuration["palette"][theme]["warning"],
                    fontsize=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
                    ),
                ),
                widget.Spacer(
                    length=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
                    )
                ),
                widgets.location.WidgetLocation(
                    r=r,
                    notification_color=configuration["palette"][theme]["highlight"],
                    fontsize=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
                    ),
                    update_interval=1,
                ),
                widget.Spacer(
                    length=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
                    )
                ),
                widgets.vpn.WidgetVPN(
                    r=r,
                    warning_color=configuration["palette"][theme]["warning"],
                    fontsize=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
                    ),
                    update_interval=1,
                ),
                widget.Spacer(
                    length=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
                    )
                ),
                widget.Clock(
                    format="%Y-%m-%d %a %H:%M:%S",
                    fontsize=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
                    ),
                ),
                widget.Chord(
                    fontsize=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
                    )
                ),
                widgets.service_state.WidgetServiceState(
                    service="nuunamnir.backend.service",
                    warning_color=configuration["palette"][theme]["warning"],
                    fontsize=int(
                        round(
                            configuration["monitors"][monitor]["scaling_factor"]
                            * configuration["font"]["size"]
                        )
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
        ),
        background=configuration["palette"][theme]["background"],
        wallpaper=wallpaper,
        wallpaper_mode="fill",
        # You can uncomment this variable if you see that on X11 floating resize/moving is laggy
        # By default we handle these events delayed to already improve performance, however your system might still be struggling
        # This variable is set to None (no cap) by default, but you can set it to 60 to indicate that you limit it to 60 events per second
        # x11_drag_polling_rate = 60,
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

# XXX: Gasp! We're lying here. In fact, nobody really uses or cares about this
# string besides java UI toolkits; you can see several discussions on the
# mailing lists, GitHub issues, and other WM documentation that suggest setting
# this string if your java app doesn't work correctly. We may as well just lie
# and say that we're a working one by default.
#
# We choose LG3D to maximize irony: it is a 3D non-reparenting WM written in
# java that happens to be on java's whitelist.
wmname = "LG3D"
