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
import os
import subprocess
import json
import math
import collections

from libqtile import bar, layout, qtile, widget, hook
from libqtile.config import Click, Drag, Group, Key, Match, Screen
from libqtile.lazy import lazy
from libqtile.utils import guess_terminal
import screeninfo
monitors = screeninfo.get_monitors()[::-1]

import widgets.power
import widgets.idle


with open(
    os.path.join(os.path.expanduser("~"), ".config", "qtile", "configuration.json"), "r"
) as input_handle:
    configuration_data = json.load(input_handle)


@hook.subscribe.startup
def _():
    subprocess.Popen(
        args=[
            "feh",
            "--bg-center",
            os.path.expanduser(
                os.path.join(
                    "~",
                    ".config",
                    "theme",
                    f"wallpaper_{configuration_data['theme-mode']}.png",
                )
            ),
        ]
    )

mod = "mod4"
terminal = guess_terminal()

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
        [mod],
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
    Key([mod, "control"], "r", lazy.reload_config(), desc="Reload the config"),
    Key([mod, "control"], "q", lazy.shutdown(), desc="Shutdown Qtile"),
    Key(
        [mod],
        "r",
        lazy.spawn("rofi -show run"),
        desc="Spawns the rofi window switcher.",
    ),
]

def divide_chunks(l, n):
    for i in range(0, len(l), n):
        yield l[i : i + n]

group_names = "12345678"[:len(monitors) * 4]
chunks = divide_chunks(group_names, math.ceil(len(group_names) / len(monitors)))
groups_by_screen = collections.defaultdict(list)
for i, chunk in enumerate(list(chunks)[::-1]):
    for name in chunk:
        groups_by_screen[i].append(name)

groups = []
for j in groups_by_screen:
    groups += [Group(i, label=l) for i, l in zip(groups_by_screen[j], ["+"] * len(groups_by_screen[j]))]

@hook.subscribe.startup_complete
def send_to_second_screen():
    chunks = divide_chunks(group_names, math.ceil(len(group_names) / len(monitors)))
    for i, chunk in enumerate(chunks):
        # qtile.groups_map[chunk[0]].cmd_toscreen(i, toggle=False)
        qtile.groups_map[chunk[0]].toscreen(i)

for i in groups:
    for screen in groups_by_screen:
        if i.name in groups_by_screen[screen]:
            break
    lazy.group[i.name].toscreen(screen)
    keys.extend(
        [
            # mod1 + letter of group = switch to group
            Key(
                [mod],
                i.name,
                lazy.group[i.name].toscreen(screen),
                desc="Switch to group {}".format(i.name),
            ),
            # mod1 + shift + letter of group = switch to & move focused window to group
            Key(
                [mod, "shift"],
                i.name,
                lazy.window.togroup(i.name, switch_group=False),
                desc="Switch to & move focused window to group {}".format(i.name),
            ),
            # Or, use below if you prefer not to switch to that group.
            # # mod1 + shift + letter of group = move focused window to group
            # Key([mod, "shift"], i.name, lazy.window.togroup(i.name),
            #     desc="move focused window to group {}".format(i.name)),
        ]
    )

layouts = [
    layout.Columns(
        border_normal=configuration_data["colors"]["inactive"],
        border_focus=configuration_data["colors"]["active"],
        border_focus_stack=configuration_data["colors"]["active"],
        border_width=1,
        margin=[0, 64, 64, 64],
    ),
    layout.Max(margin=[0, 64, 64, 64]),
    # Try more layouts by unleashing below layouts.
    # layout.Stack(num_stacks=2),
    # layout.Bsp(),
    # layout.Matrix(),
    # layout.MonadTall(),
    # layout.MonadWide(),
    # layout.RatioTile(),
    # layout.Tile(),
    # layout.TreeTab(),
    # layout.VerticalTile(),
    # layout.Zoomy(),
]

widget_defaults = dict(
    font="LiterationMono Nerd Font Mono",
    fontsize=30,
    padding=8,
    foreground=configuration_data["colors"]["foreground"],
)
extension_defaults = widget_defaults.copy()


@lazy.function
def toggle_theme_mode(qtile):
    theme_mode = "light"
    if configuration_data["theme-mode"] == "light":
        theme_mode = "dark"

    command = f"curl 'http://localhost:2106/graphql' -X POST -H 'content-type: application/json' --data '{{\"query\":\"query {{ reload_qtile(theme_mode: \\\"{theme_mode}\\\") }}\"}}'"

    subprocess.Popen(command, shell=True, universal_newlines=True)


screens = []
for i, monitor in enumerate(monitors):
    screen = Screen(
        top=bar.Bar(
            [
                widget.Spacer(length=64),
                widget.GroupBox(
                    highlight_method="text",
                    urgent_alert_method="text",
                    active=configuration_data["colors"]["active"],
                    inactive=configuration_data["colors"]["inactive"],
                    this_current_screen_border=configuration_data["colors"]["foreground"],
                    visible_groups=groups_by_screen[i],
                    hide_unused=False,
                ),
                widget.Spacer(length=64),
                widget.WindowName(),
                widgets.power.PowerGraphQLTextBox(update_interval=60),
                widget.Clock(format="%H:%M"),
                widget.Spacer(length=16),
                widgets.idle.IdleTextBox(update_interval=1),
                widget.Image(
                    filename=os.path.expanduser(
                        os.path.join(
                            "~",
                            ".config",
                            "theme",
                            f'theme-mode_{configuration_data["theme-mode"]}.svg',
                        )
                    ),
                    margin=36,
                    mouse_callbacks={"Button1": toggle_theme_mode},
                ),
                widget.Spacer(length=64),
            ],
            128,
            background=configuration_data["colors"]["background"],
            # border_width=[2, 0, 2, 0],  # Draw top and bottom borders
            # border_color=["ff00ff", "000000", "ff00ff", "000000"]  # Borders are magenta
        ),
        # You can uncomment this variable if you see that on X11 floating resize/moving is laggy
        # By default we handle these events delayed to already improve performance, however your system might still be struggling
        # This variable is set to None (no cap) by default, but you can set it to 60 to indicate that you limit it to 60 events per second
        # x11_drag_polling_rate = 60,
    )
    screens.append(screen)

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
cursor_warp = False
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
    ]
)
auto_fullscreen = True
focus_on_window_activation = "smart"
reconfigure_screens = True

# If things like steam games want to auto-minimize themselves when losing
# focus, should we respect this or not?
auto_minimize = True

# When using the Wayland backend, this can be used to configure input devices.
wl_input_rules = None

# XXX: Gasp! We're lying here. In fact, nobody really uses or cares about this
# string besides java UI toolkits; you can see several discussions on the
# mailing lists, GitHub issues, and other WM documentation that suggest setting
# this string if your java app doesn't work correctly. We may as well just lie
# and say that we're a working one by default.
#
# We choose LG3D to maximize irony: it is a 3D non-reparenting WM written in
# java that happens to be on java's whitelist.
wmname = "LG3D"
