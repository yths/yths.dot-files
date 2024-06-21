import os
import json
import tempfile
import datetime
from zoneinfo import ZoneInfo
import subprocess
import configparser

import influxdb_client
import screeninfo


# https://stackoverflow.com/questions/8299386/modifying-a-symlink-in-python/55742015#55742015
def symlink(target, link_name, overwrite=False):
    """
    Create a symbolic link named link_name pointing to target.
    If link_name exists then FileExistsError is raised, unless overwrite=True.
    When trying to overwrite a directory, IsADirectoryError is raised.
    """

    if not overwrite:
        os.symlink(target, link_name)
        return

    # os.replace() may fail if files are on different filesystems
    link_dir = os.path.dirname(link_name)

    # Create link to target with temporary filename
    while True:
        temp_link_name = tempfile.mktemp(dir=link_dir)

        # os.* functions mimic as closely as possible system functions
        # The POSIX symlink() returns EEXIST if link_name already exists
        # https://pubs.opengroup.org/onlinepubs/9699919799/functions/symlink.html
        try:
            os.symlink(target, temp_link_name)
            break
        except FileExistsError:
            pass

    # Replace link_name with temp_link_name
    try:
        # Pre-empt os.replace on a directory with a nicer message
        if not os.path.islink(link_name) and os.path.isdir(link_name):
            raise IsADirectoryError(
                f"Cannot symlink over existing directory: '{link_name}'"
            )
        os.replace(temp_link_name, link_name)
    except:
        if os.path.islink(temp_link_name):
            os.remove(temp_link_name)
        raise


def get_theme_mode():
    with open(
        os.path.join("/usr/local/bin/configurations_update_server/configuration.json"),
        "r",
    ) as f:
        configuration_data = json.load(f)
    influxdb_token = configuration_data["credentials"]["influxdb_token"]
    influxdb_url = configuration_data["influxdb"]["url"]
    influxdb_org = configuration_data["influxdb"]["org"]
    influxdb_bucket = configuration_data["influxdb"]["bucket"]

    query = f"""from(bucket: "{influxdb_bucket}")
|> range(start: 0)
|> filter(fn: (r) => r["_measurement"] == "location")
|> filter(fn: (r) => r["_field"] == "sunset" or r["_field"] == "sunrise" or r["_field"] == "timezone")
|> group()
|> sort(columns: ["_time"])"""

    read_client = influxdb_client.InfluxDBClient(
        url=influxdb_url, token=influxdb_token, org=influxdb_org
    )
    read_api = read_client.query_api()
    result = read_api.query(org=influxdb_org, query=query)

    unpacked_result = dict()
    for table in result:
        for record in table.records:
            unpacked_result[record.get_field()] = record.get_value()

    if unpacked_result:
        now = datetime.datetime.now(ZoneInfo(unpacked_result["timezone"]))
        sunrise = datetime.datetime.fromisoformat(unpacked_result["sunrise"])
        sunset = datetime.datetime.fromisoformat(unpacked_result["sunset"])
        if sunrise < now:
            if sunset > now:
                theme_mode = "light"
            else:
                theme_mode = "dark"
        else:
            if sunset > now:
                theme_mode = "light"
            else:
                theme_mode = "dark"
    else:
        now = datetime.datetime.now()
        sunrise = datetime.datetime.now()
        sunset = datetime.datetime.now()
        theme_mode = "light"

    return sunrise, sunset, now, theme_mode


def change_theme(theme_name=None):
    with open(
        os.path.expanduser(os.path.join("~", ".config", "theme.conf")), "r"
    ) as input_handle:
        configuration = json.load(input_handle)

    if theme_name is None:
        theme_name = configuration["name"]

    symlink(
        os.path.expanduser(
            os.path.join("~", "repositories", "yths.dot-files", "themes", theme_name)
        ),
        os.path.expanduser(os.path.join("~", ".config", "theme")),
        overwrite=True,
    )


def update_qtile(template=None, theme_mode=None):
    with open(
        os.path.expanduser(os.path.join("~", ".config", "qtile", "configuration.json")),
        "r",
    ) as input_handle:
        configuration = json.load(input_handle)
    configuration["colors"] = template["colors"][theme_mode]
    configuration["theme-mode"] = theme_mode
    with open(
        os.path.expanduser(os.path.join("~", ".config", "qtile", "configuration.json")),
        "w",
    ) as output_handle:
        json.dump(configuration, output_handle)


def update_kitty(template, theme_mode):
    configuration = dict()
    with open(
        os.path.expanduser(os.path.join("~", ".config", "kitty", "kitty.conf")), "r"
    ) as input_handle:
        for line in input_handle:
            if line.startswith("#"):
                continue
            line_pieces = line.rstrip().split()
            if len(line_pieces) > 1:
                if line_pieces[0] == "include":
                    continue
                configuration[line_pieces[0]] = " ".join(line_pieces[1:])

    configuration["font_family"] = template["font-family"]

    theme = {
        "background": template["colors"][theme_mode]["background"],
        "foreground": template["colors"][theme_mode]["foreground"],
    }

    with open(
        os.path.expanduser(os.path.join("~", ".config", "kitty", "kitty.conf")), "w"
    ) as output_handle:
        for key in configuration:
            output_handle.write(" ".join([key, configuration[key]]) + "\n")

    with open(
        os.path.expanduser(
            os.path.join("~", ".config", "kitty", "themes", "yths.conf")
        ),
        "w",
    ) as output_handle:
        for key in theme:
            output_handle.write(" ".join([key, theme[key]]) + "\n")

    subprocess.Popen(args=["kitty", "+kitten", "themes", "--reload-in=all", "yths"])


def update_dunst(template, theme_mode):
    configuration_path = os.path.expanduser(
        os.path.join("~", ".config", "dunst", "dunstrc")
    )
    configuration = configparser.ConfigParser()
    configuration.read(configuration_path)

    configuration["global"][
        "frame_color"
    ] = f'"{template["colors"][theme_mode]["inactive"]}"'

    configuration["urgency_critical"][
        "foreground"
    ] = f'"{template["colors"][theme_mode]["foreground"]}"'
    configuration["urgency_critical"][
        "background"
    ] = f'"{template["colors"][theme_mode]["background"]}"'

    configuration["urgency_normal"][
        "foreground"
    ] = f'"{template["colors"][theme_mode]["active"]}"'
    configuration["urgency_normal"][
        "background"
    ] = f'"{template["colors"][theme_mode]["background"]}"'

    configuration["urgency_low"][
        "foreground"
    ] = f'"{template["colors"][theme_mode]["inactive"]}"'
    configuration["urgency_low"][
        "background"
    ] = f'"{template["colors"][theme_mode]["background"]}"'

    with open(configuration_path, "w") as output_handle:
        configuration.write(output_handle)
    subprocess.run(["killall", "dunst"])


def update_rofi(template, theme_mode):
    configuration_path = os.path.expanduser(
        os.path.join("~", ".config", "rofi", "theme.rasi")
    )
    configuration = dict()
    with open(configuration_path, "r") as input_handle:
        state = "element"
        element = None
        for line in input_handle:
            raw_line = line.strip()
            if raw_line == "":
                continue
            elif raw_line.startswith("/*"):
                state = f"comment_{state}"

            if state.startswith("comment"):
                if raw_line.endswith("*/"):
                    state = state.split("_")[1]
                continue

            if state == "element":
                line_pieces = raw_line.split()
                element = " ".join(line_pieces[:-1])
                configuration[element] = dict()
                state = "property"
            elif state == "property":
                if raw_line == "}":
                    element = None
                    state = "element"
                    continue
                try:
                    property_name, property_value = raw_line.split(":")
                    configuration[element][
                        property_name.strip()
                    ] = property_value.strip()
                except ValueError:
                    continue

        configuration['*']['background-color'] = f'{template["colors"][theme_mode]["background"]};'
        configuration['*']['text-color'] = f'{template["colors"][theme_mode]["foreground"]};'

        with open(configuration_path, "w") as output_handle:
            for element in configuration:
                output_handle.write(f"{element} {{\n")
                for property_name in configuration[element]:
                    output_handle.write(
                        f"  {property_name}: {configuration[element][property_name]}\n"
                    )
                output_handle.write(f"}}\n")


def update_xresources(template, theme_mode):
    configuration = dict()
    configuration_path = os.path.expanduser(os.path.join("~", ".Xresources"))
    with open(configuration_path, "r") as input_handle:
        for line in input_handle:
            key, value = line.strip().split(":")
            configuration[key.strip()] = value.strip()

    dpi_diagonals = list()
    monitors = screeninfo.get_monitors()
    for monitor in monitors:
        diagonal_mm = (monitor.width_mm**2 + monitor.height_mm**2) ** 0.5
        diagonal = (monitor.width**2 + monitor.height**2) ** 0.5

        diagonal_in = diagonal_mm / 25.4
        try:
            dpi_diagonal = int(round(diagonal / diagonal_in))
        except ZeroDivisonError:
            dpi_diagonal = 96
        dpi_diagonals.append(dpi_diagonal)

    configuration["Xft.dpi"] = str(max(dpi_diagonals)) 
        
    with open(configuration_path, "w") as output_handle:
        for key in configuration:
            l = "{}: {}\n".format(key, configuration[key])
            print(l)
            output_handle.write(l)


def update_gtk(template, theme_mode):
    configuration_path = os.path.expanduser(os.path.join("~", ".config", "gtk-3.0", "settings.ini"))
    configuration = configparser.ConfigParser()
    configuration.read(configuration_path)

    configuration["Settings"]["gtk-application-prefer-dark-theme"] = "true" if theme_mode == "dark" else "false"

    with open(configuration_path, 'w') as output_handle:
        configuration.write(output_handle)


def update_all(theme_mode=None):
    if theme_mode is None:
        _, _, _, theme_mode = get_theme_mode()

    with open(
        os.path.expanduser(os.path.join("~", ".config", "theme", "template.json")), "r"
    ) as input_handle:
        template = json.load(input_handle)
    update_kitty(template, theme_mode)
    update_dunst(template, theme_mode)
    update_rofi(template, theme_mode)
    update_gtk(template, theme_mode)
    update_qtile(template, theme_mode)


if __name__ == "__main__":
    # print(get_theme_mode())
    print(update_xresources(None, None))
