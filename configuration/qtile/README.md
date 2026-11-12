# Qtile Configuration

Everything qtile loads: the configuration it starts from, the bar cells it renders, and the
code those cells share. `install.py` symlinks this whole directory to `~/.config/qtile/`, so
the installed configuration is these files, live — editing one here changes the running
desktop at the next restart.

## What Is Here

| Path | Holds |
|---|---|
| `config.py` | keybindings, groups, layouts, screens, and the bar's widget list |
| [`widgets/`](widgets/README.md) | one module per bar cell |
| [`shared/`](shared/README.md) | code more than one cell needs |

`config.py` reads `~/.config/config.json` at startup for the palette, font and monitor
geometry, and opens one Redis connection pool that it passes to every cell. Cells never open
their own.

## Imports

`widgets` and `shared` resolve as plain imports — `import widgets.audio`,
`import shared.stream` — because qtile puts this directory on `sys.path` before loading
`config.py`. Neither needs an `__init__.py`, and neither is importable from outside a qtile
session without adding this directory to the path first.

## Restarting

```bash
qtile cmd-obj -o cmd -f restart
```

Configuration errors do not appear on screen: qtile falls back to its default configuration
and writes the traceback to `~/.local/share/qtile/qtile.log`. To check a change before
restarting, load it the same way qtile does:

```bash
cd ~/.config/qtile && python -c "import sys; sys.path.insert(0, '.'); import config"
```
