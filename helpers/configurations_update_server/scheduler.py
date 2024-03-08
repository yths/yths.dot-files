import os
import json
import subprocess
import datetime
from zoneinfo import ZoneInfo

import updater


def schedule():
    sunrise, sunset, now, theme_mode = updater.get_theme_mode()

    with open(
        os.path.join("/usr/local/bin/configurations_update_server/configuration.json"),
        "r",
    ) as f:
        configuration_data = json.load(f)

    unit_name = "reload_"
    schedule = None
    if sunrise > now:
        schedule = sunrise.strftime("%Y-%m-%d %H:%M:%S")
        unit_name = "sunrise_" + unit_name + schedule.replace(" ", "")
    else:
        if sunset > now:
            schedule = sunset.strftime("%Y-%m-%d %H:%M:%S")
            unit_name = "sunset_" + unit_name + schedule.replace(" ", "")

    server_port = configuration_data["server"]["port"]

    if schedule is not None:
        command = f'systemd-run --on-calendar "{schedule}" --no-ask-password --user -u {unit_name} curl \'http://localhost:{server_port}/graphql\' -X POST -H \'content-type: application/json\' --data \'{{"query":"query {{ reload_qtile(theme_mode: \\"{theme_mode}\\") }}"}}\''
        subprocess.run(command, shell=True, universal_newlines=True)


if __name__ == "__main__":
    schedule()
