# Kitty Configuration

Every file in this directory is generated. Nothing here is source, and an edit made here
survives until the next theme switch.

`install.py` symlinks this directory to `~/.config/kitty/`, so what kitty reads *is* this
directory. That is why the generated files are gitignored: without that, a day/night switch
rewrote tracked files twice a day and `git status` stopped meaning anything.

| File | Written by |
|---|---|
| `kitty.conf` | `helper/patch_kitty.py` — remote control, audio bell, font size |
| `themes/<preset>.conf` | `helper/patch_kitty.py` — the palette mapped onto kitty's sixteen ANSI slots |
| `current-theme.conf` | `kitty +kitten themes`, which copies the active preset's file here |

## Changing Something

Edit `helper/patch_kitty.py`, then apply it:

```bash
python helper/patch_kitty.py
```

A setting that is not palette-derived — a keybinding, a scrollback limit — goes in that
script's `patched_configuration` dict, so it survives regeneration. Adding one to
`kitty.conf` by hand does not.

## One Thing to Know

`patch_kitty.py` writes `kitty.conf` without the `BEGIN_KITTY_THEME` block, and
`kitty +kitten themes` puts it back. A full theme switch runs both, so the file ends up
correct. Running the patcher alone leaves kitty without its `include current-theme.conf`
until the kitten runs — so prefer `helper/patch_configurations.py`, which does the whole
sequence, over calling this patcher on its own.
