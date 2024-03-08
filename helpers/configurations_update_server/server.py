import os
import json

import waitress

import cus
import scheduler
import updater


if __name__ == "__main__":
    updater.change_theme()
    scheduler.schedule()

    with open(
        os.path.join("/usr/local/bin/configurations_update_server/configuration.json"),
        "r",
    ) as f:
        configuration_data = json.load(f)
    server_port = configuration_data["server"]["port"]

    waitress.serve(cus.app, host="0.0.0.0", port=server_port)
