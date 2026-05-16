"""Orchestrate patching of per-app configurations from the active theme.

``patch_all`` reads ``~/.config/config.json`` (the active theme bundle's metadata) and
calls the per-target patchers (plymouth, web-greeter, vscode) in order so every app picks
up the current palette. Invoked when the theme is switched or the palette is regenerated.
"""

import json
import os
import subprocess
import configparser
import time

import toml

from helper.patch_web_greeter import patch_web_greeter


def patch_rofi(configuration):
    theme = configuration["state"]["theme"]

    widths = list()
    scaling_factors = list()
    for monitor in configuration["monitors"]:
        widths.append(configuration["monitors"][monitor]["width"])
        scaling_factors.append(configuration["monitors"][monitor]["scaling_factor"])
    average_width = int(round(sum(widths) / len(widths)))
    average_scaling_factor = sum(scaling_factors) / len(scaling_factors)

    patched_configuration = {
        "FONT": f'"{configuration["font"]["family"]} {int(round(configuration["font"]["size"] * 1.214))}"',
        "COLOR0": f"{configuration['palette'][theme]['background']}",
        "COLOR1": f"{configuration['palette'][theme]['neutral']}",
        "COLOR2": f"{configuration['palette'][theme]['failure']}",
        "COLOR3": f"{configuration['palette'][theme]['foreground']}",
        "COLOR4": f"{configuration['palette'][theme]['highlight']}",
        "WIDTH": f"{average_width}px",
        "YOFFSET": f"{int(round(configuration['font']['size'] * average_scaling_factor * 2.75))}px",
    }
    with open(
        os.path.expanduser("~/.config/rofi/theme_config.rasi"), "w"
    ) as output_handle:
        output_handle.write("* {\n")
        for key, value in patched_configuration.items():
            output_handle.write(f"    {key}: {value};\n")
        output_handle.write("}\n")
    print("Patched rofi configuration ...")


def patch_xorg(configuration):
    dpis = []
    with open(os.path.expanduser("~/.Xresources"), "w") as output_handle:
        for monitor in configuration["monitors"]:
            dpis.append(configuration["monitors"][monitor]["diagonal_dpi"])
        average_dpi = int(round(sum(dpis) / len(dpis)))
        output_handle.write(f"Xft.dpi: {average_dpi}\n")
    print(f"Patched .Xresources with average DPI: {average_dpi}.")


def patch_kitty(configuration):
    theme = configuration["state"]["theme"]
    patched_configuration = {
        "allow_remote_control": "yes",
        "enable_audio_bell": "no",
        "font_size": int(round(configuration["font"]["size"] * 0.714)),
        #"include": "current-theme.conf",
    }
    with open(os.path.expanduser("~/.config/kitty/kitty.conf"), "w") as output_handle:
        for key, value in patched_configuration.items():
            output_handle.write(f"{key} {value}\n")

    patched_configuration = {
        "background": configuration["palette"][theme]["background"],
        "selection_background": configuration["palette"][theme]["foreground"],
        "foreground": configuration["palette"][theme]["foreground"],
        "selection_foreground": configuration["palette"][theme]["background"],
        "font_family": configuration["font"]["family"],
        "cursor": configuration["palette"][theme]["foreground_variant"],

        # black = 0/8
        # red = 1/9
        # green = 2/10
        # yellow = 4/12 3/11
        # blue = 3/11 4/12
        # magenta = 5/13
        # cyan = 6/14
        # white = 7/15

        "color0": configuration["palette"][theme]["foreground_variant"],
        "color1": configuration["palette"][theme]["red"],
        "color2": configuration["palette"][theme]["green"],
        "color3": configuration["palette"][theme]["yellow"],
        "color4": configuration["palette"][theme]["blue"],
        "color5": configuration["palette"][theme]["magenta"],
        "color6": configuration["palette"][theme]["cyan"],
        "color7": configuration["palette"][theme]["background"],
        "color8": configuration["palette"][theme]["foreground"],
        "color9": configuration["palette"][theme]["red_variant"],
        "color10": configuration["palette"][theme]["green_variant"],
        "color11": configuration["palette"][theme]["yellow_variant"],
        "color12": configuration["palette"][theme]["blue_variant"],
        "color13": configuration["palette"][theme]["magenta_variant"],
        "color14": configuration["palette"][theme]["cyan_variant"],
        "color15": configuration["palette"][theme]["neutral"],
    }
    with open(
        os.path.expanduser(f"~/.config/kitty/themes/{configuration['name']}.conf"), "w"
    ) as output_handle:
        for key, value in patched_configuration.items():
            output_handle.write(f"{key} {value}\n")

    print("Patched kitty configuration ...")


def patch_tmux(configuration):
    configuration_path = os.path.expanduser("~/.config/tmux/tmux.conf")

    theme = configuration["state"]["theme"]
    output = list()
    with open(configuration_path, "r") as input_handle:
        for line in input_handle:
            if line.startswith("color"):
                continue
            output.append(line)

    patched_configuration = {
        "color0": configuration["palette"][theme]["background"],
        "color1": configuration["palette"][theme]["neutral"],
        "color2": configuration["palette"][theme]["highlight"],
        "color3": configuration["palette"][theme]["foreground"],
    }

    with open(configuration_path, "w") as output_handle:
        for key, value in patched_configuration.items():
            output_handle.write(f"{key}={value}\n")
        for line in output:
            output_handle.write(line)
    print("Patched tmux configuration ...")


def patch_starship(configuration):
    configuration_path = os.path.expanduser("~/.config/starship.toml")

    theme = configuration["state"]["theme"]
    with open(configuration_path, "r") as input_handle:
        starship_configuration = toml.load(input_handle)

    starship_configuration["palettes"]["theme"]["color0"] = configuration["palette"][theme]["foreground"]
    starship_configuration["palettes"]["theme"]["color1"] = configuration["palette"][theme]["foreground_variant"]
    starship_configuration["palettes"]["theme"]["color2"] = configuration["palette"][theme]["success"]
    starship_configuration["palettes"]["theme"]["color3"] = configuration["palette"][theme]["failure"]
    starship_configuration["palettes"]["theme"]["color4"] = configuration["palette"][theme]["highlight"]

    with open(configuration_path, "w") as output_handle:
        toml.dump(starship_configuration, output_handle)
    print("Patched starship configuration ...")


def patch_dunst(configuration):
    configuration_path = os.path.expanduser("~/.config/dunst/dunstrc")

    theme = configuration["state"]["theme"]
    with open(configuration_path, "r") as input_handle:
        dunst_configuration = configparser.ConfigParser(interpolation=None)
        dunst_configuration.read_file(input_handle)

    dunst_configuration["global"]["foreground"] = f'"{configuration["palette"][theme]["foreground"]}"'
    dunst_configuration["global"]["background"] = f'"{configuration["palette"][theme]["background"]}"'
    dunst_configuration["global"]["separator_color"] = f'"{configuration["palette"][theme]["background"]}"'
    dunst_configuration["global"]["font"] = f'"{configuration["font"]["family"]} {int(round(configuration["font"]["size"] * 0.714))}"'

    scaling_factors = list()
    for monitor in configuration["monitors"]:
        scaling_factors.append(configuration["monitors"][monitor]["scaling_factor"])
    average_scaling_factor = sum(scaling_factors) / len(scaling_factors)
    dunst_configuration["global"]["offset"] = f'0x{int(round(configuration["font"]["size"] * average_scaling_factor * 3))}'

    dunst_configuration["urgency_normal"]["foreground"] = f'"{configuration["palette"][theme]["foreground"]}"'
    dunst_configuration["urgency_normal"]["format"] = f"\" <span foreground='{configuration["palette"][theme]["notification"]}'>%s</span>\\n  %b\""

    dunst_configuration["urgency_critical"]["foreground"] = f'"{configuration["palette"][theme]["foreground"]}"'
    dunst_configuration["urgency_critical"]["format"] = f"\" <span foreground='{configuration["palette"][theme]["warning"]}'>%s</span>\\n  %b\""

    dunst_configuration["urgency_low"]["foreground"] = f'"{configuration["palette"][theme]["foreground"]}"'
    dunst_configuration["urgency_low"]["format"] = f"\" <span foreground='{configuration["palette"][theme]["neutral"]}'>%s</span>\\n  %b\""

    with open(configuration_path, "w") as output_handle:
        dunst_configuration.write(output_handle)
    print("Patched dunst configuration ...")


def patch_all(configuration):
    patch_rofi(configuration)
    patch_xorg(configuration)
    patch_kitty(configuration)
    patch_tmux(configuration)
    patch_starship(configuration)
    patch_dunst(configuration)
    patch_web_greeter(configuration)


with open(os.path.expanduser("~/.config/config.json"), "r") as input_handle:
    configuration = json.load(input_handle)
patch_all(configuration)

subprocess.call(args=["killall", "dunst"])
subprocess.call(
    args=[
        "tmux",
        "source-file",
        os.path.expanduser(os.path.join("~", ".config", "tmux", "tmux.conf")),
    ]
)
subprocess.call(args=["kitty", "+kitten", "themes", "--reload-in=all", configuration['name']])
subprocess.call(args=["kill", "-1", "`pgrep qutebrowser`"])
subprocess.call(args=["python", os.path.expanduser(os.path.join("~", ".config", "qtile", "widgets", "patch_vsc.py")), "--mode", configuration["state"]["theme"], "--input-path", os.path.expanduser(os.path.join("~", ".config", "qtile", "widgets"))])
subprocess.call(args=["qtile", "cmd-obj", "-o", "cmd", "-f", "restart"])
subprocess.call(args=["notify-send", "-u", "normal", "Patching", "All configurations reloaded ..."])
