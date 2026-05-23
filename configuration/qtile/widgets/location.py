"""Qtile widget: IP-derived geolocation with current sunrise/sunset.

Reads the latest entry from the ``location`` Redis stream (latitude, longitude, timezone,
sunrise, sunset) and surfaces the day/night transition that drives the automatic theme
switch. ``BackgroundPoll`` based.
"""

import datetime
import json
import os
import subprocess

import libqtile.log_utils
import libqtile.widget.base
import redis.exceptions


class WidgetLocation(libqtile.widget.base.InLoopPollText):
    def __init__(self, r, notification_color="#ff0000", configuration_file_path=os.path.expanduser(os.path.join("~", ".config", "config.json")), **config):
        libqtile.widget.base.InLoopPollText.__init__(self, **config)
        self.r = r
        self.configuration_file_path = configuration_file_path

        self.notification_color = notification_color

        self.add_callbacks({"Button2": self.toggle_mode, "Button3": self.toggle_theme_manually})

    def toggle_mode(self):
        with open(self.configuration_file_path, "r") as f:
            configuration = json.load(f)
        if configuration['state']['mode'] == "automatic":
            configuration['state']['mode'] = "manual"
        else:
            configuration['state']['mode'] = "automatic"
        with open(self.configuration_file_path, "w") as f:
            json.dump(configuration, f)

    def toggle_theme_manually(self):
        with open(self.configuration_file_path, "r") as f:
            configuration = json.load(f)
        configuration['state']['mode'] = "manual"
        with open(self.configuration_file_path, "w") as f:
            json.dump(configuration, f)

        self.toggle_theme()

    def toggle_theme(self):
        with open(self.configuration_file_path, "r") as f:
            configuration = json.load(f)
        if configuration['state']['theme'] == "light":
            configuration['state']['theme'] = "dark"
        else:
            configuration['state']['theme'] = "light"

        
        with open(self.configuration_file_path, "w") as f:
            json.dump(configuration, f)
        # execute patch script
        subprocess.Popen(args=["python", os.path.expanduser(os.path.join("~", ".config", "qtile", "widgets", "patch_configurations.py"))])
        # subprocess.Popen(args=["pkill", "-SIGUSR1", "qtile"])

    def poll(self):
        if self.r is None:
            return ""
        
        with open(self.configuration_file_path, "r") as f:
            configuration = json.load(f)

        try:
            data = self.r.xrevrange("location", count=1)
        except redis.exceptions.RedisError:
            return ""
        try:
            eid, payload = data[-1]
        except IndexError:
            return ""
        measurement = json.loads(payload.get(b"measurement").decode("utf-8"))

        sunrise = measurement.get("sunrise", 0)
        sunset = measurement.get("sunset", 0)

        # convert sunrise and sundset to timestamps
        sunrise_ts = datetime.datetime.strptime(sunrise, '%H:%M:%S').time()
        sunset_ts = datetime.datetime.strptime(sunset, '%H:%M:%S').time()

        now = datetime.datetime.now().time()

        if now < sunrise_ts or now > sunset_ts:
            theme = "dark"
        else:
            theme = "light"

        if theme != configuration['state']['theme'] and configuration['state']['mode'] == "automatic":
            # trigger reload
            self.toggle_theme()

        if configuration['state']['mode'] == "manual":
            mode_icon = " "
        else:
            mode_icon = ""

        if now < sunrise_ts or now > sunset_ts:
            return f"<span color='{self.notification_color}'> {sunrise}</span>  {sunset}{mode_icon}"
        else:
            return f" {sunrise} <span color='{self.notification_color}'> {sunset}</span>{mode_icon} "