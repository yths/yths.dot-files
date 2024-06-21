import os
import sys
import json

import requests
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS

if __name__ == "__main__":
    power_supply = "GRID"
    charge_full = 100000000
    charge = 100000000
    status = "Full"
    try:
        try:
            with open(os.path.join("/usr/local/bin/sss_power.json"), "r") as f:
                configuration_data = json.load(f)
        except:
            with open(os.path.join("sss_power.json"), "r") as f:
                configuration_data = json.load(f)

        influxdb_token = configuration_data["credentials"]["influxdb_token"]
        influxdb_url = configuration_data["influxdb"]["url"]
        influxdb_org = configuration_data["influxdb"]["org"]
        influxdb_bucket = configuration_data["influxdb"]["bucket"]
        try:
            with open("/sys/class/power_supply/BAT0/charge_full", "r") as input_handle:
                charge_full = int(input_handle.read().strip())
            with open("/sys/class/power_supply/BAT0/charge_now", "r") as input_handle:
                charge = int(input_handle.read().strip())
            with open("/sys/class/power_supply/BAT0/status", "r") as input_handle:
                status = input_handle.read().strip()

            power_supply = "BAT0"
            print(charge_full, charge, status)

        except Exception:
            pass

        write_client = influxdb_client.InfluxDBClient(
            url=influxdb_url, token=influxdb_token, org=influxdb_org
        )
        write_api = write_client.write_api(write_options=SYNCHRONOUS)

        point = (
            influxdb_client.Point("power")
            .tag("power", power_supply)
            .field("charge_full", charge_full)
            .field("charge", charge)
            .field("status", status)
        )

        write_api.write(bucket=influxdb_bucket, org=influxdb_org, record=point)
    except:
        sys.exit(1)
