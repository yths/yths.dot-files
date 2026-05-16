# LightDM Theme

Two themes for [nody-greeter](https://github.com/JezerM/nody-greeter):

- `themes/nuunamnir` — minimal terminal-style prompt
- `themes/standard` — full UI with user list, sessions, power, layout, battery, brightness

Both consume CSS variables generated from `~/.config/config.json` by `helper/patch_web_greeter.py`. Shared greeter logic lives in `themes/_shared/logic.js` and is copied into each theme during the patch step so deployed themes under `/usr/share/web-greeter/themes/` are self-contained.

## Patch

After changing palette/font/state in the global config, regenerate the greeter:

```bash
python helper/patch_web_greeter.py
```

This is also invoked by `helper/patch_configurations.py:patch_all`.

## Deploy

```bash
sudo cp -RL configuration/web-greeter/themes/nuunamnir /usr/share/web-greeter/themes/nuunamnir
sudo cp -RL configuration/web-greeter/themes/standard  /usr/share/web-greeter/themes/standard
```

Then set the active theme in `/etc/lightdm/web-greeter.yml`.

## Preview

A dev server lets you exercise the themes in a regular browser, with mocked `window.lightdm` and live theme.json editing.

```bash
sudo pacman -S python-websockets        # or: pip install -r ../../requirements-dev.txt
python configuration/web-greeter/preview/server.py
xdg-open http://127.0.0.1:8765/
```

See [`preview/README.md`](preview/README.md) for the verification checklist.
