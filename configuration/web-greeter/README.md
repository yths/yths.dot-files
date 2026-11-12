# Web-Greeter Themes

The login screen LightDM shows before the desktop starts. Each theme is a directory under
`themes/` containing an HTML page and a stylesheet, rendered by web-greeter in a browser
engine.

A theme never contains colours of its own. It declares CSS variable names in its
`theme.json`, and `helper/patch_web_greeter.py` fills them from the active palette into a
generated `theme.css`. Shared greeter logic lives in `themes/_shared/` and is copied into
each theme during that step, so a deployed theme is self-contained. A directory whose name
starts with `_` is a shared-asset bundle, not a theme.

Writing one is described in [THEME-DEVELOPMENT.md](THEME-DEVELOPMENT.md); iterating on one
without logging out is described in [preview/](preview/README.md).

## Patch

After changing palette, font, or state in `~/.config/config.json`, regenerate every theme's `theme.css`:

```bash
python helper/patch_web_greeter.py
```

This is also invoked by `helper/patch_configurations.py:patch_all`.

## Deploy

```bash
sudo cp -RL configuration/web-greeter/themes/<theme-name> /usr/share/web-greeter/themes/<theme-name>
```

Then set the active theme in `/etc/lightdm/web-greeter.yml`.
