import argparse
import json
import os
import configparser

import subprocess

import loguru
import PIL.Image

import cairo


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Patch plymouth configurations according to the given configuration file.")
    parser.add_argument("--configuration", type=str, help="Path to the configuration file.", required=False, default="~/.config/config.json", dest="configuration_file_path")
    parser.add_argument("--theme", type=str, help="Theme to be applied.", required=False, default="dark", dest="theme")
    parser.add_argument("plymouth_path", type=str, help="Path to the plymouth theme file to be patched.")
    args = parser.parse_args()

    with open(os.path.expanduser(args.configuration_file_path), "r") as config_handle:
        configuration = json.load(config_handle)

    loguru.logger.info(f"Patching plymouth theme at '{args.plymouth_path}' with theme '{args.theme}' ...")
    
    plymouth_configuration = configparser.ConfigParser(interpolation=None)
    plymouth_configuration.optionxform = str
    plymouth_configuration.read(os.path.join(args.plymouth_path, "yths.plymouth"))
    
    plymouth_configuration["two-step"]["Font"] = f"{configuration['font']['family']} {int(round(configuration['font']['size'] * 1.25))}"
    plymouth_configuration["two-step"]["TitleFont"] = f"{configuration['font']['family']} {int(round(configuration['font']['size'] * 1.25))}"
    plymouth_configuration["two-step"]["MonospaceFont"] = f"{configuration['font']['family']} {int(round(configuration['font']['size'] * 0.85))}"

    plymouth_configuration["two-step"]["BackgroundStartColor"] = f"{configuration['palette'][args.theme]['background'].replace('#', '0x')}"
    plymouth_configuration["two-step"]["BackgroundEndColor"] = f"{configuration['palette'][args.theme]['background'].replace('#', '0x')}"
    plymouth_configuration["two-step"]["ProgressBarBackgroundColor"] = f"{configuration['palette'][args.theme]['neutral'].replace('#', '0x')}"
    plymouth_configuration["two-step"]["ConsoleLogTextColor"] = f"{configuration['palette'][args.theme]['foreground'].replace('#', '0x')}"
    plymouth_configuration["two-step"]["ConsoleLogBackgroundColor"] = f"{configuration['palette'][args.theme]['background'].replace('#', '0x')}"

    plymouth_configuration.write(open(os.path.join(args.plymouth_path, "yths.plymouth"), "w"), space_around_delimiters=False)

    # find path to font file
    proc = subprocess.run(["fc-list"], encoding='utf-8', stdout=subprocess.PIPE)
    for line in proc.stdout.split("\n"):
        try:
            font_path, font_name, font_style = line.split(":")
            path_value = font_path.strip()
            name_value = font_name.split(",")[0].strip()
            if name_value != configuration["font"]["family"]:
                continue
            style_values = font_style.split("=")[1].split(",")
            if "Regular" not in style_values or len(style_values) > 1:
                continue
        except ValueError:
            continue

    im_entry = PIL.Image.new("RGB", (305, 34), configuration['palette'][args.theme]["background"])
    im_entry.save(os.path.join(args.plymouth_path, "entry.png"))

    im_entry = PIL.Image.new("RGB", (533, 400), configuration['palette'][args.theme]["background"])
    im_entry.save(os.path.join(args.plymouth_path, "animation-001.png"))

    color_neutral_str = configuration['palette'][args.theme]["highlight"]
    color_neutral_tuple = tuple(int(color_neutral_str[i:i+2], 16) for i in (1, 3, 5))

    color_foreground_str = configuration['palette'][args.theme]["foreground"]
    color_foreground_tuple = tuple(int(color_foreground_str[i:i+2], 16) for i in (1, 3, 5))

    color_grey_str = configuration['palette'][args.theme]["neutral"]
    color_grey_tuple = tuple(int(color_grey_str[i:i+2], 16) for i in (1, 3, 5))

    with cairo.ImageSurface(cairo.FORMAT_ARGB32, 24, 28) as surface:
        context = cairo.Context(surface)
        context.set_source_rgb(*[v / 255 for v in color_neutral_tuple])
        context.select_font_face(configuration["font"]["family"], cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(24)
        context.move_to(6, 22)
        context.show_text("󰌎")
        surface.write_to_png(os.path.join(args.plymouth_path, "capslock.png"))

    with cairo.ImageSurface(cairo.FORMAT_ARGB32, 10, 10) as surface:
        context = cairo.Context(surface)
        context.set_source_rgb(*[v / 255 for v in color_foreground_tuple])
        context.select_font_face(configuration["font"]["family"], cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(16)
        context.move_to(1, 11)
        context.show_text("•")
        surface.write_to_png(os.path.join(args.plymouth_path, "bullet.png"))

    with cairo.ImageSurface(cairo.FORMAT_ARGB32, 64, 64) as surface:
        context = cairo.Context(surface)
        context.set_source_rgb(*[v / 255 for v in color_foreground_tuple])
        context.select_font_face(configuration["font"]["family"], cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(32)
        context.move_to(24, 44)
        context.show_text("")
        surface.write_to_png(os.path.join(args.plymouth_path, "throbber-01.png"))

    with cairo.ImageSurface(cairo.FORMAT_ARGB32, 64, 64) as surface:
        context = cairo.Context(surface)
        context.set_source_rgb(*[v / 255 for v in color_grey_tuple])
        context.select_font_face(configuration["font"]["family"], cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(32)
        context.move_to(24, 44)
        context.show_text("")
        surface.write_to_png(os.path.join(args.plymouth_path, "throbber-02.png"))

    with cairo.ImageSurface(cairo.FORMAT_ARGB32, 36, 36) as surface:
        context = cairo.Context(surface)
        context.set_source_rgb(*[v / 255 for v in color_grey_tuple])
        context.select_font_face(configuration["font"]["family"], cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(32)
        context.move_to(2, 30)
        context.show_text("")
        surface.write_to_png(os.path.join(args.plymouth_path, "keyboard.png"))

    with cairo.ImageSurface(cairo.FORMAT_ARGB32, 35, 34) as surface:
        context = cairo.Context(surface)
        context.set_source_rgb(*[v / 255 for v in color_grey_tuple])
        context.select_font_face(configuration["font"]["family"], cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(32)
        context.move_to(3, 29)
        context.show_text("󰟵")
        surface.write_to_png(os.path.join(args.plymouth_path, "lock.png"))