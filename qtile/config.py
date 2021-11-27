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
import asyncio
import json
import subprocess

from typing import List  # noqa: F401

import time
import requests

from libqtile import hook, qtile
from libqtile.widget import base
class GraphQLBatteryWidget(base.InLoopPollText):
    defaults = [
        ('update_interval', 60., 'Update interval for the battery widget.')
    ]
    def __init__(self, url='http://localhost:2106/graphql', **config):
        base.InLoopPollText.__init__(self, **config)
        self.add_defaults(GraphQLBatteryWidget.defaults)
        self.url = url

        self.history = list()
        self.history_state = None

    def tick(self):
        self.update(self.poll())
        return self.update_interval - time.time() % self.update_interval

    def poll(self):
        r = requests.post(self.url, json={'query': 'query{battery{state, charge, charger_connected}}'})
        data = json.loads(r.text)

        charge = data['data']['battery']['charge']
        charge_raw = float(charge.split(' ')[0])

        charger_connected_str = ''
        if data['data']['battery']['charger_connected']:
            charger_connected_str = 'ﮣ'

        battery_state_str = ''
        if data['data']['battery']['state'] == 'Charging':
            if self.history_state is None or self.history_state == 'Discharging':
                self.history = list()
                self.history_state = 'Charging'
            battery_state_str = '▴'
        elif data['data']['battery']['state'] == 'Discharging':
            if self.history_state is None or self.history_state == 'Charging':
                self.history = list()
                self.history_state = 'Discharging'
            battery_state_str = '▾'

        self.history.append([time.time(), charge_raw])
        if len(self.history) > 1:
            duration = self.history[-1][0] - self.history[0][0]
            charge_delta = abs(self.history[-1][1] - self.history[-2][1])
            charge_rate = charge_delta / duration
            time_remaining = str(charge_rate)
            if charge_rate == 0:
                time_remaining = ''
            else:
                if self.history_state == 'Charging':
                    time_remaining_seconds = (100 - charge_raw) / charge_rate
                else:
                    time_remaining_seconds = charge_raw / charge_rate
                time_remaining_hours = int(time_remaining_seconds // 3600)
                time_remaining_minutes = int((time_remaining_seconds - (3600 * time_remaining_hours)) // 60)
                time_remaining = str(time_remaining_hours).zfill(2) + ':' + str(time_remaining_minutes).zfill(2)
        else:
            time_remaining = ''

        return f'‎{charger_connected_str} {time_remaining} {charge} {battery_state_str}'

class GraphQLAudioWidget(base.InLoopPollText):
    defaults = [
        ('update_interval', .25, 'Update interval for the audio widget.')
    ]
    def __init__(self, url='http://localhost:2106/graphql', **config):
        base.InLoopPollText.__init__(self, **config)
        self.add_defaults(GraphQLAudioWidget.defaults)
        self.url = url

    def tick(self):
        self.update(self.poll())
        return self.update_interval - time.time() % self.update_interval

    def poll(self):
        try:
             audio_icon = '蓼'
             audio_level = str(subprocess.check_output(['pamixer', '--get-volume-human']).decode('utf-8')).rstrip().replace('%',  ' %')
        except subprocess.CalledProcessError:
            audio_icon = '遼'
            audio_level = str(subprocess.check_output(['pamixer', '--get-volume']).decode('utf-8')).rstrip() + ' %'

        return f"{audio_icon} {audio_level}"


from libqtile import bar, layout, widget
from libqtile.config import Click, Drag, Group, Key, Match, Screen
from libqtile.lazy import lazy
from libqtile.utils import guess_terminal

mod = "mod4"
terminal = "kitty" # guess_terminal()

@hook.subscribe.startup_once
def autostart():
    home = os.path.expanduser('~')
    subprocess.Popen([home + '/startup_once.sh'])

keys = [
    # Switch between windows
    Key([mod], "h", lazy.layout.left(), desc="Move focus to left"),
    Key([mod], "l", lazy.layout.right(), desc="Move focus to right"),
    Key([mod], "j", lazy.layout.down(), desc="Move focus down"),
    Key([mod], "k", lazy.layout.up(), desc="Move focus up"),
    Key([mod], "space", lazy.layout.next(),
        desc="Move window focus to other window"),

    # Move windows between left/right columns or move up/down in current stack.
    # Moving out of range in Columns layout will create new column.
    Key([mod, "shift"], "h", lazy.layout.shuffle_left(),
        desc="Move window to the left"),
    Key([mod, "shift"], "l", lazy.layout.shuffle_right(),
        desc="Move window to the right"),
    Key([mod, "shift"], "j", lazy.layout.shuffle_down(),
        desc="Move window down"),
    Key([mod, "shift"], "k", lazy.layout.shuffle_up(), desc="Move window up"),

    # Grow windows. If current window is on the edge of screen and direction
    # will be to screen edge - window would shrink.
    Key([mod, "control"], "h", lazy.layout.grow_left(),
        desc="Grow window to the left"),
    Key([mod, "control"], "l", lazy.layout.grow_right(),
        desc="Grow window to the right"),
    Key([mod, "control"], "j", lazy.layout.grow_down(),
        desc="Grow window down"),
    Key([mod, "control"], "k", lazy.layout.grow_up(), desc="Grow window up"),
    Key([mod], "n", lazy.layout.normalize(), desc="Reset all window sizes"),

    # Toggle between split and unsplit sides of stack.
    # Split = all windows displayed
    # Unsplit = 1 window displayed, like Max layout, but still with
    # multiple stack panes
    Key([mod, "shift"], "Return", lazy.layout.toggle_split(),
        desc="Toggle between split and unsplit sides of stack"),
    Key([mod], "Return", lazy.spawn(terminal), desc="Launch terminal"),

    # Toggle between different layouts as defined below
    Key([mod, 'control'], "Tab", lazy.next_layout(), desc="Toggle between layouts"),
    Key([mod], 'Tab', lazy.next_screen(), desc='Next monitor'),
    Key([mod], "w", lazy.window.kill(), desc="Kill focused window"),

    Key([mod, "shift", "control"], "l",
        lazy.spawn("betterlockscreen -l"),
        desc="Lock screen"
        ),
    Key([mod, "control"], "r", lazy.restart(), desc="Restart Qtile"),
    Key([mod, "control"], "q", lazy.shutdown(), desc="Shutdown Qtile"),
    Key([mod], "r", lazy.spawncmd(),
        desc="Spawn a command using a prompt widget"),

    # Brightness
    Key([], "XF86MonBrightnessDown", lazy.spawn('brightnessctl s 100-')),
    Key([], "XF86MonBrightnessUp", lazy.spawn('brightnessctl s 100+')),

    # # Volume
    Key([], "XF86AudioMute", lazy.spawn('pamixer -t')),
    Key([], "XF86AudioLowerVolume", lazy.spawn('pamixer --allow-boost -d 1')),
    Key([], "XF86AudioRaiseVolume", lazy.spawn('pamixer --allow-boost -i 1')),
]

# Groups with matches

workspaces = [
    {"name": " ₁", "key": "1", "matches": [], "layout": "stack"},
    {"name": " ₂", "key": "2", "matches": [], "layout": "stack"},
    {"name": " ₃", "key": "3", "matches": [], "layout": "stack"},
    {"name": " ₄", "key": "4", "matches": [], "layout": "stack"},
    {"name": " ₅", "key": "5", "matches": [], "layout": "stack"},
    {"name": " ₆", "key": "6", "matches": [], "layout": "stack"},
]

groups = []
for workspace in workspaces:
    matches = workspace["matches"] if "matches" in workspace else None
    layouts = workspace["layout"] if "layout" in workspace else None
    groups.append(Group(workspace["name"], matches=matches, layout=layouts))
    keys.append(Key([mod], workspace["key"], lazy.group[workspace["name"]].toscreen()))
    keys.append(Key([mod, "shift"], workspace["key"], lazy.window.togroup(workspace["name"])))

groupbox_config = {
    #'active': foreground,
    'highlight_method': 'line',
    #'this_current_screen_border': colour_focussed,
    #'other_current_screen_border': colours[5],
    #'highlight_color': [background, colours[5]],
    'disable_drag': True,
    #'padding': 4,
    'font': 'SauceCodePro Nerd Font',
    'fontsize': 32,
}

groupboxes = [
    widget.GroupBox(**groupbox_config, visible_groups=[' ₁', ' ₂', ' ₃']),
    widget.GroupBox(**groupbox_config, visible_groups=[' ₄', ' ₅', ' ₆']),
]

@hook.subscribe.startup
def _():
    # Set up initial GroupBox visible groups
    if len(qtile.screens) > 1:
        groupboxes[0].visible_groups = [' ₁', ' ₂', ' ₃']
    else:
        groupboxes[0].visible_groups = [' ₁', ' ₂', ' ₃', ' ₄', ' ₅', ' ₆']

@hook.subscribe.screen_change
async def _(_):
    # Reconfigure GroupBox visible groups
    await asyncio.sleep(1)  # Am I gonna fix this?
    if len(qtile.screens) > 1:
        groupboxes[0].visible_groups = [' ₁', ' ₂', ' ₃']
    else:
        groupboxes[0].visible_groups = [' ₁', ' ₂', ' ₃', ' ₄', ' ₅', ' ₆']
    if hasattr(groupboxes[0], 'bar'):
        groupboxes[0].bar.draw()


layout_theme = {"border_width": 8,
                "margin": 8,
                "border_focus": '#000000',
                "border_normal": '#000000',
                }

layouts = [
    layout.Columns(**layout_theme),
    # layout.Max(**layout_theme),
    layout.Stack(num_stacks=1, **layout_theme),
    # Try more layouts by unleashing below layouts.
    # layout.Stack(num_stacks=2),
    # layout.Bsp(),
    # layout.Matrix(),
    # layout.MonadTall(),
    # layout.MonadWide(),
    # layout.RatioTile(),
    # layout.Tile(),
    # layout.TreeTab(**layout_theme),
    # layout.VerticalTile(),
    # layout.Zoomy(columnwidth=256, **layout_theme),
]

widget_defaults = dict(
    font='SauceCodePro Nerd Font',
    fontsize=32,
)
extension_defaults = widget_defaults.copy()

screens = [
    Screen(
        top=bar.Bar(
            [
                widget.Spacer(length=16),
                groupboxes[0],
                widget.Prompt(),
                widget.WindowName(),
                widget.Chord(
                    chords_colors={
                        'launch': ("#ff0000", "#ffffff"),
                    },
                    name_transform=lambda name: name.upper(),
                ),
                widget.KeyboardLayout(fmt=' {}', configured_keyboards=['de']),
                widget.Clock(format='%Y-%m-%d %a %H:%M:%S'),
                widget.Spacer(length=16),
                GraphQLAudioWidget(),
                widget.Spacer(length=16),
                GraphQLBatteryWidget(),
                widget.Spacer(length=16),
            ],
            64, margin=[8, 8, 0, 8], background='#000000',
            wallpaper="~/Pictures/Wallpapers/wallpaper.jpg",
            wallpaper_mode='fill',
        ),
    ),

    Screen(
        top=bar.Bar(
            [
                widget.Spacer(length=16),   
                groupboxes[1],            
                widget.WindowName(),
                widget.Chord(
                    chords_colors={
                        'launch': ("#ff0000", "#ffffff"),
                    },
                    name_transform=lambda name: name.upper(),
                ),                
                widget.Spacer(length=16),
            ],
            64, margin=[8, 8, 0, 8], background='#000000',
            wallpaper="~/Pictures/Wallpapers/wallpaper.jpg",
            wallpaper_mode='fill',
        ),
    ),
]

# Drag floating layouts.
mouse = [
    Drag([mod], "Button1", lazy.window.set_position_floating(),
         start=lazy.window.get_position()),
    Drag([mod], "Button3", lazy.window.set_size_floating(),
         start=lazy.window.get_size()),
    Click([mod], "Button2", lazy.window.bring_to_front())
]

dgroups_key_binder = None
dgroups_app_rules = []  # type: List
follow_mouse_focus = True
bring_front_click = False
cursor_warp = False
floating_layout = layout.Floating(float_rules=[
    # Run the utility of `xprop` to see the wm class and name of an X client.
    *layout.Floating.default_float_rules,
    Match(wm_class='confirmreset'),  # gitk
    Match(wm_class='makebranch'),  # gitk
    Match(wm_class='maketag'),  # gitk
    Match(wm_class='ssh-askpass'),  # ssh-askpass
    Match(title='branchdialog'),  # gitk
    Match(title='pinentry'),  # GPG key password entry
])
auto_fullscreen = True
focus_on_window_activation = "smart"
reconfigure_screens = True

# If things like steam games want to auto-minimize themselves when losing
# focus, should we respect this or not?
auto_minimize = True

# XXX: Gasp! We're lying here. In fact, nobody really uses or cares about this
# string besides java UI toolkits; you can see several discussions on the
# mailing lists, GitHub issues, and other WM documentation that suggest setting
# this string if your java app doesn't work correctly. We may as well just lie
# and say that we're a working one by default.
#
# We choose LG3D to maximize irony: it is a 3D non-reparenting WM written in
# java that happens to be on java's whitelist.
wmname = "LG3D"
