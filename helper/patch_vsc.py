"""Patch the user's Visual Studio Code ``settings.json``.

Maps the active palette's semantic tokens to VSCode editor colors and token colors using
perceptual nearest-color matching (``colour`` library, sRGB → XYZ → ΔE). Handles both
light and dark variants from the active theme bundle.
"""

import argparse
import collections
import json
import os
import pickle

import colour

import utils


def color_str_to_tuple(s):
    return tuple(int(s[i : i + 2], 16) / 255 for i in (1, 3, 5))


def closest_color(v: str, colors, lookup_colors=None) -> str:
    if lookup_colors is None:
        lookup_colors = colors
    if len(v) == 9:
        alpha = v[7:9]
        v = v[:7]
    else:
        alpha = ""
    v_rgb = color_str_to_tuple(v)
    v_xyz = colour.sRGB_to_XYZ(v_rgb)
    v_cam16 = colour.XYZ_to_CAM16UCS(v_xyz)
    min_delta_E = float("inf")
    best_color = v
    for color in colors:
        delta_E = colour.delta_E(
            v_cam16, color["cam16"], method="CAM16-UCS"
        )
        if delta_E < min_delta_E:
            min_delta_E = delta_E
            for lookup_color in lookup_colors:
                if lookup_color["label"] == color["label"]:
                    best_color = lookup_color["hex"]
                    break
    v = best_color + alpha
    return v

def dict_replace_value(d: dict, colors, lookup_colors=None) -> dict:
    if lookup_colors is None:
        lookup_colors = colors
    x = {}
    for k, v in d.items():
        if isinstance(v, dict):
            v = dict_replace_value(v, colors, lookup_colors)
        elif isinstance(v, list):
            v = list_replace_value(v, colors, lookup_colors)
        elif isinstance(v, str):
            if v.startswith("#") and (len(v) == 7 or len(v) == 9):
                v = closest_color(v, colors, lookup_colors)
        x[k] = v
    return x


def list_replace_value(l: list, colors, lookup_colors=None) -> list:
    if lookup_colors is None:
        lookup_colors = colors
    x = []
    for e in l:
        if isinstance(e, list):
            e = list_replace_value(e, colors, lookup_colors)
        elif isinstance(e, dict):
            e = dict_replace_value(e, colors, lookup_colors)
        elif isinstance(e, str):
            if e.startswith("#") and (len(e) == 7 or len(e) == 9):
                e = closest_color(e, colors, lookup_colors)
        x.append(e)
    return x


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--theme-pickle-path",
        type=str,
        default=os.path.join("~", ".config", "palette.pkl"),
        help="Path to the theme pickle file.",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["dark", "light"],
        default="dark",
        help="Color mode to patch.",
    )
    parser.add_argument(
        "--method",
        type=str,
        choices=["nearest_neighbor", "reference"],
        default="nearest_neighbor",
        help="Method by which the colors of the theme are mapped to the Visual Studio Code configuration.",
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default=None,
        help="Path to save the patched Visual Studio Code settings. If not provided, will not output.",
    )
    parser.add_argument(
        "--input-path",
        type=str,
        default=None,
        help="Path to load the Visual Studio Code settings from. If not provided, will use the current working directory.",
    )
    args = parser.parse_args()

    colors = pickle.load(
        open(os.path.expanduser(args.theme_pickle_path), "rb")
    )

    colors_map = collections.defaultdict(list)
    for mode in ["dark", "light"]:
        for label in colors[mode]:
            color_rgb = color_str_to_tuple(colors[mode][label])
            color_xyz = colour.sRGB_to_XYZ(color_rgb)
            color_cam16 = colour.XYZ_to_CAM16UCS(color_xyz)
            colors_map[mode].append(
                {"label": label, "hex": colors[mode][label], "cam16": color_cam16}
            )

    default_config = {}
    for mode in ["dark", "light"]:
        input_path = args.input_path
        if input_path is None:
            input_path = os.getcwd()
        with open(os.path.join(input_path, f"vsc_default_{mode}.json"), "r") as input_handle:
            default_config[mode] = json.load(input_handle)

    patched_config_dark = default_config['dark'].copy()
    patched_config_light = default_config['light'].copy()

    patched_config_dark["name"] = "nuunamnir (dark)"
    patched_config_light["name"] = "nuunamnir (light)"

    if args.method == "nearest_neighbor":
        patched_config_dark = dict_replace_value(patched_config_dark, colors_map["dark"])
        patched_config_light = dict_replace_value(patched_config_light, colors_map["light"])
    else:
        patched_config_dark = dict_replace_value(patched_config_dark, colors_map["dark"])
        patched_config_light = dict_replace_value(patched_config_light, colors_map["light"], colors_map["dark"])


    if args.mode == "dark":
        utils.logger.info("Patching Visual Studio Code settings to dark theme...")
        target_config = patched_config_dark
    else:
        utils.logger.info("Patching Visual Studio Code settings to light theme...")
        target_config = patched_config_light

    if os.path.exists(os.path.expanduser("~/.config/Code/User/settings.json")):
        utils.logger.info("Patching Visual Studio Code settings...")
        with open(
            os.path.expanduser("~/.config/Code/User/settings.json"), "r"
        ) as input_handle:
            user_config = json.load(input_handle)
            user_config["editor.tokenColorCustomizations"] = {
                "textMateRules": target_config.get(
                    "tokenColors", []
                )
            }
            user_config["workbench.colorCustomizations"] = target_config.get(
                "colors", {}
            )
        with open(
            os.path.expanduser("~/.config/Code/User/settings.json"), "w"
        ) as output_handle:
            json.dump(user_config, output_handle, indent=4)
        utils.logger.info("Patched Visual Studio Code settings.")

    if args.output_path is not None:
        output_path = os.path.expanduser(args.output_path)
        utils.logger.info(f"Saving patched Visual Studio Code settings to {output_path}...")
        with open(os.path.join(output_path, "vsc_patched_dark.json"), "w") as output_handle:
            json.dump(patched_config_dark, output_handle, indent=4)

        with open(os.path.join(output_path, "vsc_patched_light.json"), "w") as output_handle:
            json.dump(patched_config_light, output_handle, indent=4)
