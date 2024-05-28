## Features
* get external ip address, ip address based location and sun rise and set time
* get power supply information
* get connected bluetooth devices and their battery level
* get cpu and gpu temperature

## Dependencies
The InlfuxDB service and client need to be installed, configured and running on the system.
```
yay -S influxdb python-influxdb-client python-requests
```

## Installation
Make the required changes to the configuration file. Copy the script and its configuration file to `/usr/local/bin` and make the script executable.
```
cp /home/yths/repositories/yths.dot-files/helpers/system_statistics_server/sss_location.* /usr/local/bin/
chmod +x /usr/local/bin/sss_location.py
```
Copy the `sss_location.service` and `sss_location.timer` file to `/etc/systemd/system` and enable and start the service.
```
cp /home/yths/repositories/yths.dot-files/helpers/system_statistics_server/sss_location.{service,timer} /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now sss_location.timer
```