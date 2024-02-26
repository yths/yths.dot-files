## Dependencies
```
yay -S python-waitress python-flask python-graphene
cd dependencies/python_graphql_server_core_pre_release
makepkg -si
```

## Installation
Copy the `configuration_update_server` folder to `/usr/local/bin` and make appropritate adjustments to `configuration.json`. Then copy `cus.{service,timer}` to `/etc/systemd/user` and enable the service:
```
systemctl enable --now --user cus.timer
systemctl status --user cus.timer
```