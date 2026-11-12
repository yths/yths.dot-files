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

## Installing

Themes are authored here and read from `/usr/share/web-greeter/themes/`, which is
root-owned, so patching and installing are separate stages. `./bootstrap.sh` does both;
by hand it is:

```bash
python helper/patch_web_greeter.py --install --activate
```

`--install` copies the patched theme into place, dereferencing the wallpaper symlink because
the greeter runs before login and cannot read out of a home directory. `--activate` points
LightDM at it by rewriting the value on the `theme:` line of `/etc/lightdm/web-greeter.yml`
and nothing else in that file — it is LightDM's, and carries settings this repository has no
opinion about. Without `--activate` the theme is installed and whatever is already active
stays active.

`--theme <name>` installs one other than `standard`.
