import sys
import json

import requests
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS

if __name__ == '__main__':
    try:
        with open(os.path.join('/usr/local/bin/sss_location.json'), 'r') as f:
            configuration_data = json.load(f)

        influxdb_token = configuration_data['credentials']['influxdb_token']
        ipinfo_token = configuration_data['credentials']['ipinfo_token']
        influxdb_url = configuration_data['influxdb']['url']
        influxdb_org = configuration_data['influxdb']['org']
        influxdb_bucket = configuration_data['influxdb']['bucket']

        ip_address = requests.get('https://ident.me').content.decode('utf-8')
        location_data = requests.get(f"https://ipinfo.io/{ip_address}?token={ipinfo_token}").json()
        lat, lng = location_data['loc'].split(',')
        tzid = location_data['timezone']
        sun_data = requests.get(f'https://api.sunrise-sunset.org/json?lat={lat}&lng={lng}&tzid={tzid}&formatted=0').json()
        sun_rise = sun_data['results']['sunrise']
        sun_set = sun_data['results']['sunset']

        write_client = influxdb_client.InfluxDBClient(url=influxdb_url, token=influxdb_token, org=influxdb_org)
        write_api = write_client.write_api(write_options=SYNCHRONOUS)

        point = influxdb_client.Point("location") \
            .tag("location", ip_address) \
            .field("latitude", float(lat)) \
            .field("longitude", float(lng)) \
            .field("timezone", tzid) \
            .field("sunrise", sun_rise) \
            .field("sunset", sun_set)

        write_api.write(bucket=influxdb_bucket, org="assur", record=point)
    except:
        sys.exit(1)