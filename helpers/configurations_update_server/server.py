import os
import json

import waitress

import cus
import scheduler


if __name__ == '__main__':
    with open(os.path.join('configuration.json'), 'r') as f:
        configuration_data = json.load(f)
    server_port = configuration_data['server']['port']

    scheduler.schedule()

    waitress.serve(cus.app, host='0.0.0.0', port=server_port)