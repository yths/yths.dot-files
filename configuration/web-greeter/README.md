# LightDM Themes

The web-greeter themes that LightDM renders at the login screen. For authoring a new theme, see [THEME-DEVELOPMENT.md](THEME-DEVELOPMENT.md); for the iteration workflow, see [preview/README.md](preview/README.md); for where the greeter fits in the system, see [../../docs/architecture.md](../../docs/architecture.md).

Themes live as directories under `themes/`. Each theme consumes CSS variables generated from `~/.config/config.json` by `helper/patch_web_greeter.py`; shared greeter logic lives in `themes/_shared/logic.js` and is copied into every theme during the patch step so deployed themes under `/usr/share/web-greeter/themes/` are self-contained. Directories whose name starts with `_` are shared-asset bundles, not themes.

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
