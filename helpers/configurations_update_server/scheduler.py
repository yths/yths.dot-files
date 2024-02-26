import os
import json
import subprocess
import datetime
from zoneinfo import ZoneInfo

import influxdb_client


def schedule():
    query = '''from(bucket: "sss_location")
|> range(start: 0)
|> filter(fn: (r) => r["_measurement"] == "location")
|> filter(fn: (r) => r["_field"] == "sunset" or r["_field"] == "sunrise" or r["_field"] == "timezone")
|> last()'''
    with open(os.path.join('/usr/local/bin/configurations_update_server/configuration.json'), 'r') as f:
            configuration_data = json.load(f)

    influxdb_token = configuration_data['credentials']['influxdb_token']
    influxdb_url = configuration_data['influxdb']['url']
    influxdb_org = configuration_data['influxdb']['org']
    influxdb_bucket = configuration_data['influxdb']['bucket']
    
    read_client = influxdb_client.InfluxDBClient(url=influxdb_url, token=influxdb_token, org=influxdb_org)
    read_api = read_client.query_api()
    result = read_api.query(org=influxdb_org, query=query)

    unpacked_result = dict()
    for table in result:
        for record in table.records:
            unpacked_result[record.get_field()] = record.get_value()

    
    now = datetime.datetime.now(ZoneInfo(unpacked_result['timezone']))
    sunrise = datetime.datetime.fromisoformat(unpacked_result['sunrise'])
    sunset = datetime.datetime.fromisoformat(unpacked_result['sunset'])
    unit_name = "reload_"
    if sunrise > now:
        schedule = sunrise.strftime('%Y-%m-%d %H:%M:%S')
        unit_name = "sunrise_" + unit_name + schedule.replace(' ', '')
    else:
        if sunset > now:
            schedule = sunset.strftime('%Y-%m-%d %H:%M:%S')
            unit_name = "sunset_" + unit_name + schedule.replace(' ', '')

    server_port = configuration_data['server']['port']

    subprocess.run(["systemd-run", f'--on-calendar', schedule, "--no-ask-password", "--user", "-u", unit_name, "curl", "-g", "-X", "POST", "-H", "Content-Type: application/json", "-d", '{"query":"query{reload_qtile}"}', f"http://localhost:{server_port}/graphql"])


if __name__ == '__main__':
    schedule()