import subprocess
import os
import json

import graphene
import influxdb_client

import scheduler
import updater


class Power(graphene.ObjectType):
    status = graphene.String()
    charge = graphene.Int()
    charge_full = graphene.Int(name="charge_full")


class Query(graphene.ObjectType):
    class Meta:
        description = "The API for the configuration update server."

    reload_qtile = graphene.Boolean(
        name="reload_qtile",
        description="Reload the qtile configuration.",
        theme_mode=graphene.String(
            name="theme_mode",
            description="Set the theme mode, can be light or dark.",
            default_value="dark",
        ),
    )

    power = graphene.Field(Power)

    def resolve_power(root, info):
        with open(
            os.path.join(
                "/usr/local/bin/configurations_update_server/configuration.json"
            ),
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

        query = """from(bucket: "sss_location")
|> range(start: 0)
|> filter(fn: (r) => r["_measurement"] == "power")
|> filter(fn: (r) => r["_field"] == "status" or r["_field"] == "charge" or r["_field"] == "charge_full")
|> last()"""

        result = read_api.query(org=influxdb_org, query=query)

        unpacked_result = dict()
        for table in result:
            for record in table.records:
                unpacked_result[record.get_field()] = record.get_value()

        return Power(
            status=unpacked_result["status"],
            charge=unpacked_result["charge"],
            charge_full=unpacked_result["charge_full"],
        )

    def resolve_reload_qtile(root, info, theme_mode):
        scheduler.schedule()
        diff = {
            "theme-mode": theme_mode,
        }
        updater.update_qtile(diff)
        subprocess.run(["qtile", "cmd-obj", "-o", "cmd", "-f", "reload_config"])
        return True


schema = graphene.Schema(query=Query)


if __name__ == "__main__":
    pass
