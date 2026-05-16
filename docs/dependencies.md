# Dependencies

Every third-party Python package this repo imports, the Arch package that provides it, and which entry point pulls it in. The only blessed install path is `yay -S` — see [install.md](install.md) for the full setup commands.

This page is the audit reference. When adding a new third-party import to the code, add a row here **and** update the relevant `yay -S` command in [install.md](install.md). When removing a dependency, delete its row and prune it from install.md the same way.

## Naming Convention

Arch ships most Python packages as `python-<name>`. Exceptions worth memorising:

- `import PIL` → `python-pillow`
- `import cairo` → `python-pycairo`
- `import colour` → `python-colour-science` (AUR)
- `import libqtile` → `qtile` (the window manager package brings the library)

Other AUR-only packages are marked **(AUR)** in the tables below; the rest are in the main repos.

## `install.py` (Core Installer)

| Python import | Arch package | Required? |
|---|---|---|
| `screeninfo` | `python-screeninfo` | yes |
| `loguru` | `python-loguru` | optional — falls back to stdlib `logging` |

## Patchers (`helper/patch_*.py`)

| Python import | Arch package | Used by | Notes |
|---|---|---|---|
| `loguru` | `python-loguru` | `patch_plymouth` | optional; stdlib `logging` fallback |
| `PIL` | `python-pillow` | `patch_plymouth` | renders boot background |
| `cairo` | `python-pycairo` | `patch_plymouth` | renders boot background |
| `colour` | `python-colour-science` **(AUR)** | `patch_vsc` | perceptual nearest-color matching |
| `toml` | `python-toml` | `patch_configurations` | reads `pyproject.toml`-style configs |

## qtile and Widgets (`configuration/qtile/`)

| Python import | Arch package | Required by | Notes |
|---|---|---|---|
| `libqtile` | `qtile` | window manager + all widgets | the window manager package brings the library |
| `redis` | `python-redis` | `config.py`, every widget | optional at import — widgets degrade if Redis is unreachable |
| `numpy` | `python-numpy` | `widgets/audio.py` | level-meter math |
| `sounddevice` | `python-sounddevice` **(AUR)** | `widgets/audio.py` | live audio sampling |

`python-dbus-fast` is a runtime dependency of qtile itself (not an import in this repo). Install it alongside `qtile` per [install.md](install.md).

## Web-Greeter Preview Server (`configuration/web-greeter/preview/server.py`)

| Python import | Arch package | Notes |
|---|---|---|
| `websockets` | `python-websockets` | live `theme.json` editing + reload broadcast |

## System Packages (Non-Python)

Listed here for completeness; the canonical install command is in [install.md](install.md). These do not have "Python imports" — they're services or runtimes the dot files depend on.

| Arch package | Role |
|---|---|
| `valkey` | Redis-compatible server consumed by qtile widgets and the backend service |
| `xorg-server`, `xorg-xinit` | X11 |
| `qtile` | window manager (also provides `libqtile`) |
| `ttc-iosevka` | the font referenced in `~/.config/config.json` |
| `lightdm`, `nody-greeter` | login screen + web-greeter runtime |
| `plymouth` | boot splash |
| `pacman-contrib`, `yay` | needed for the backend service's pacman post-transaction hook |

## Adding a New Dependency

1. Add the `import` to the relevant Python file.
2. Add a row to the matching table above.
3. Add the Arch package name to the corresponding `yay -S` command in [install.md](install.md).
4. If the import is optional with a fallback, mark it explicitly in the *Required?* / *Notes* column.

## Removing a Dependency

1. Delete the row here.
2. Remove the Arch package from the matching `yay -S` command in [install.md](install.md), unless the package is still pulled in by another import.

## Auditing the Table

There is no automated import scanner yet; the [issues.md](issues.md) tracker carries a ticket to extend `helper/gendocs.py` with one. Until that lands, occasional manual audits via:

```bash
grep -rhE '^import |^from .* import' install.py helper/ configuration/ | grep -vE 'helper\.|widgets\.|libqtile\.' | sort -u
```

reveal every import; the diff against this page is the audit result.
