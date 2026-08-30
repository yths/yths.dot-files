# Kitty Configuration

Every file in this directory is generated. Nothing here is source, and an edit made here
survives until the next theme switch.

`install.py` symlinks this directory to `~/.config/kitty/`, so what kitty reads *is* this
directory. That is why the generated files are gitignored: without that, a day/night switch
rewrote tracked files twice a day and `git status` stopped meaning anything.

| File | Written by |
|---|---|
| `kitty.conf` | `helper/patch_kitty.py` — base settings and the palette on kitty's sixteen ANSI slots, in one file |

## Changing Something

Edit `helper/patch_kitty.py`, then apply it:

```bash
python helper/patch_kitty.py
```

A setting that is not palette-derived — a keybinding, a scrollback limit — goes in that
script's `BASE_SETTINGS` dict, so it survives regeneration. Adding one to `kitty.conf` by
hand does not.

## One Thing to Know

Writing `kitty.conf` is the whole of applying the theme. kitty watches that file and
re-reads it about a tenth of a second after it changes, so every open window changes colour
on its own — nothing is signalled, and no window is restarted. `auto_reload_config` in
`BASE_SETTINGS` is what buys that, and it is written explicitly rather than left to kitty's
default because kitty reads it once at startup and ignores it on reload: it has to already
be in the file kitty starts with.

This is why the palette is in `kitty.conf` itself rather than an `include`d theme file, and
why nothing calls `kitty +kitten themes`. kitty watches only the config paths it was given
at startup, not the files those include — so a palette in an included file would change
without kitty noticing. The kitten did notice, but it also rewrote `kitty.conf` to add the
`include` and left a `kitty.conf.bak` beside it, both inside this repository.
