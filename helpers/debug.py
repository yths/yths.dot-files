import os
import json
import logging

import influxdb_client
import urllib3.exceptions

if __name__ == "__main__":
    # check availability of InfluxDB
    # check availability of GraphQL

    query_power =       'from(bucket:"{influxdb_bucket}")\
                         |> range(start: -30d)\
                         |> filter(fn:(r) => r._measurement == "power" and r._field == "status") \
                         |> group() \
                         |> last()'

    query_location =    'from(bucket:"{influxdb_bucket}")\
                         |> range(start: -30d)\
                         |> filter(fn:(r) => r._measurement == "location" and r._field == "timezone") \
                         |> group() \
                         |> last()'

    for configuration_file_path, query in [
        (os.path.join("system_statistics_server", "sss_location.json"), query_location),
        (os.path.join("system_statistics_server", "sss_power.json"), query_power)
    ]:
        with open(configuration_file_path, "r") as input_handle:
            configuration_data = json.load(input_handle)
            influxdb_token = configuration_data["credentials"]["influxdb_token"]
            influxdb_url = configuration_data["influxdb"]["url"]
            influxdb_org = configuration_data["influxdb"]["org"]
            influxdb_bucket = configuration_data["influxdb"]["bucket"]

            try:
                client = influxdb_client.InfluxDBClient(
                    url=influxdb_url, token=influxdb_token, org=influxdb_org
                )
                query_api = client.query_api()
                result = query_api.query(org=influxdb_org, query=query.format(influxdb_bucket=influxdb_bucket))
            except urllib3.exceptions.NewConnectionError:
                print(f"\033[91mERROR\033[0m\tcould not reach \"{influxdb_url}\"")
                continue

            print(f"\033[92mSUCCESS\033[0m\tInfluxDB\tconnected to \"{influxdb_url}\"")
            for table in result:
                for record in table.records:
                    print(f"\033[90mINFO\033[0m\tInfluxDB\tlast data point for \"{record['_measurement']}\" created on \"{record['_time']}\"")
