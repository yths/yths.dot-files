# Timezone

The system timezone follows the machine's location. The bar's sunrise/sunset cell
(`configuration/qtile/widgets/location.py`) reads the IP-derived timezone that
yths.backend-service publishes, and when it differs from the system's, runs
`timedatectl --no-ask-password set-timezone <zone>`. Every program, not just the bar clock,
then shows local time.

A location looked up while the VPN was connected is the exit server's, so those readings are
skipped and the newest one taken without the VPN is used instead. With none, the timezone is
left as it is.

`timedatectl` needs authorisation, and systemd's default is an administrator password every
time, which a bar cell cannot answer. [50-dot-files-timezone.rules](50-dot-files-timezone.rules)
grants exactly one action — `org.freedesktop.timedate1.set-timezone` — to members of `wheel`
in an active local session. `python install.py --system` installs it into
`/etc/polkit-1/rules.d/`; on its own:

```bash
python helper/patch_timezone.py --install
```

Without the rule, nothing prompts: the cell's attempt is refused, logged once, and the
timezone stays where it was. To stop following the location, delete the rule:

```bash
sudo rm /etc/polkit-1/rules.d/50-dot-files-timezone.rules
```
