import os
import json
import tempfile
import datetime
from zoneinfo import ZoneInfo
import subprocess

import influxdb_client


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


def change_theme(theme_name=None):
    if theme_name is None:
        theme_name = os.environ.get("theme")

    symlink(
        os.path.expanduser(
            os.path.join("~", "repositories", "yths.dot-files", "themes", theme_name)
        ),
        os.path.expanduser(os.path.join("~", ".config", "theme")),
        overwrite=True,
    )


def update_qtile(diff):
    with open(
        os.path.expanduser(os.path.join("~", ".config", "qtile", "configuration.json")),
        "r",
    ) as input_handle:
        configuration = json.load(input_handle)
    for k in diff:
        configuration[k] = diff[k]
    with open(
        os.path.expanduser(os.path.join("~", ".config", "qtile", "configuration.json")),
        "w",
    ) as output_handle:
        json.dump(configuration, output_handle)


def get_theme_mode():
    query = """from(bucket: "sss_location")
|> range(start: 0)
|> filter(fn: (r) => r["_measurement"] == "location")
|> filter(fn: (r) => r["_field"] == "sunset" or r["_field"] == "sunrise" or r["_field"] == "timezone")
|> group()
|> sort(columns: ["_time"])"""
    with open(
        os.path.join("/usr/local/bin/configurations_update_server/configuration.json"),
        "r",
    ) as f:
        configuration_data = json.load(f)

    influxdb_token = configuration_data["credentials"]["influxdb_token"]
    influxdb_url = configuration_data["influxdb"]["url"]
    influxdb_org = configuration_data["influxdb"]["org"]
    influxdb_bucket = configuration_data["influxdb"]["bucket"]

    read_client = influxdb_client.InfluxDBClient(
        url=influxdb_url, token=influxdb_token, org=influxdb_org
    )
    read_api = read_client.query_api()
    result = read_api.query(org=influxdb_org, query=query)

    unpacked_result = dict()
    for table in result:
        for record in table.records:
            unpacked_result[record.get_field()] = record.get_value()

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
        
    return sunrise, sunset, now, theme_mode


def update_kitty(template, theme_mode):
    configuration = dict()
    with open(os.path.expanduser(os.path.join('~', '.config', 'kitty', 'kitty.conf')), 'r') as input_handle:
        for line in input_handle:
            if line.startswith('#'):
                continue
            line_pieces = line.rstrip().split()
            if len(line_pieces) > 1:
                if line_pieces[0] == "include":
                    continue
                configuration[line_pieces[0]] = " ".join(line_pieces[1:])

    configuration["font_family"] = template["font-family"]

    theme = {
        "background": template["colors"][theme_mode]["background"],
        "foreground": template["colors"][theme_mode]["foreground"]
    }

    with open(os.path.expanduser(os.path.join('~', '.config', 'kitty', 'kitty.conf')), 'w') as output_handle:
        for key in configuration:
            output_handle.write(' '.join([key, configuration[key]]) + '\n')

    with open(os.path.expanduser(os.path.join('~', '.config', 'kitty', 'themes', 'yths.conf')), 'w') as output_handle:
        for key in theme:
            output_handle.write(' '.join([key, theme[key]]) + '\n')
    
    subprocess.Popen(args=["kitty", "+kitten", "themes", "--reload-in=all", "yths"])




def update_all():
    _, _, _, theme_mode = get_theme_mode()

    with open(os.path.expanduser(os.path.join('~', '.config', 'theme', 'template.json')), 'r') as input_handle:
        template = json.load(input_handle)
    update_kitty(template, theme_mode)
    # update_qtile(diff)


if __name__ == "__main__":
    update_all()
    quit()
    diff = {"theme-mode": "dark"}
    update_qtile(diff)
