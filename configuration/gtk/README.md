# GTK Configuration

Two directories, one per toolkit version, because GTK keeps them apart and reads a different
file from each. `install.py` symlinks both into `~/.config/`, so what GTK reads *is* this
directory — which is why the generated files are gitignored.

| File | Written by |
|---|---|
| `gtk-3.0/gtk.css`, `gtk-4.0/gtk.css` | `helper/patch_gtk.py` — the palette |
| `gtk-3.0/settings.ini`, `gtk-4.0/settings.ini` | `helper/patch_gtk.py` — theme name, font, and whether to prefer dark |

Two more settings are not files at all. Whether the file chooser lists hidden entries, and
which colour scheme GTK 4 follows, are GSettings — they live in dconf, which is per-user
binary state this repository cannot track. `patch_gtk.py` applies them instead, on every
theme switch, so a machine whose dconf was reset gets them back rather than staying wrong.

## Changing Something

Edit `helper/patch_gtk.py`, then apply it:

```bash
python helper/patch_gtk.py
```

Colours go in its `ROLES` table, which names what a colour is *for* rather than which palette
token it happens to be. A new rule goes in `RULES`, and should be added sparingly: each one
overrides a stock theme that is otherwise coherent, and a bad rule breaks an application's
layout in a way nothing here would notice.

## One Thing to Know

A user `@define-color` does **not** override a stock theme's own definition. Redefining
`theme_bg_color` in `gtk-3.0/gtk.css` leaves an Adwaita window exactly as it was — measured by
rendering one and sampling it: still `#F6F5F4`. GTK 4's built-in theme behaves the same way.
Ordinary CSS rules *do* win, because the user stylesheet is loaded after the theme, and that
is what actually carries the palette.

libadwaita is the exception: it resolves its named colours at runtime, so `@define-color
window_bg_color` works there and is the documented way to recolour it. `gtk-4.0/gtk.css` gets
both, since an application on that version may be either.

| | `@define-color` only | explicit rule |
|---|---|---|
| GTK 3 Adwaita | unchanged | applied |
| GTK 4 built-in | unchanged | applied |
| libadwaita | applied | — |

Light and dark is a fourth mechanism. GTK 3 reads `gtk-application-prefer-dark-theme` from
`settings.ini` **at startup**; GTK 4 and libadwaita watch the `color-scheme` GSettings key and
follow it live. So a running GTK 3 application keeps the scheme it started with until it is
restarted, and there is nothing here that can tell it otherwise.
