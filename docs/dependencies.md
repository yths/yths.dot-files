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
| `loguru` | `python-loguru` | every patcher, via `helper/utils.py` | optional; the fallback to stdlib `logging` is defined once, in `utils.py`, and the patchers import `logger` from there |
| `PIL` | `python-pillow` | `patch_plymouth` | renders boot background |
| `cairo` | `python-pycairo` | `patch_plymouth` | renders boot background |
| `colour` | `python-colour-science` **(AUR)** | `patch_vsc`, `list_colors` | perceptual nearest-color matching (`list_colors` reuses it for the drift report) |
| `toml` | `python-toml` | `patch_configurations` | reads `pyproject.toml`-style configs |

## qtile and Widgets (`configuration/qtile/`)

| Python import | Arch package | Required by | Notes |
|---|---|---|---|
| `libqtile` | `qtile` | window manager + all widgets | the window manager package brings the library |
| `redis` | `python-redis` | `config.py`, eight of the nine widgets | optional at import — widgets degrade if Redis is unreachable; `service_state.py` uses no Redis |
| `numpy` | `python-numpy` | `shared/spectrum.py`, `widgets/audio.py`, `helper/preview_audio.py` | level-meter math |
| `sounddevice` | `python-sounddevice` **(AUR)** | `widgets/audio.py`, `helper/preview_audio.py` | live audio sampling |

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
| `displaycal` | **optional** — provides `dispwin`, which `~/.xinitrc` uses to load display colour profiles. Without it the desktop runs uncalibrated; nothing fails |

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

## Development Tooling

The tables above track *runtime imports*. Linting is a different category — nothing in the
repo imports it — so it gets its own row here rather than being squeezed into a table whose
column headings do not fit.

| Tool | Arch package | Used for |
|---|---|---|
| `ruff` | `ruff` | lint and type-annotation enforcement across all hand-written Python |

```bash
yay -S ruff
ruff check .          # must exit 0
ruff check . --fix    # apply the safe fixes
```

## The Pre-Commit Gate

`helper/hooks/pre-commit` runs both checks and refuses the commit if either fails.

Git will not let a repository configure its own hooks. `core.hooksPath` is local
configuration, deliberately outside version control, so that cloning a repository can never
run code its author chose. The cost of that safety is that every fresh clone starts with the
gate off and nothing says so — the checks are simply never run. Arming it is one idempotent
command:

```bash
helper/hooks/enable
```

`install.py` runs it, so a normal install already arms the gate. Run it again whenever you
like; it also repairs a clone whose hooks point somewhere else. To confirm:

```bash
git config --get core.hooksPath    # helper/hooks
```

The gate runs `ruff check .` and `python helper/gendocs.py --check` against the working tree
— not the staged snapshot — because the qtile configuration is loaded live from this tree,
so a clean tree is the property worth defending. It fires from any subdirectory: a relative
`core.hooksPath` is resolved against the top of the working tree, not the current directory.
`git commit --no-verify` bypasses it for one commit.

The gate is a git hook and not a CI workflow by choice. This repository is a single-author
dotfiles tree whose working copy *is* the running desktop — qtile loads its configuration
live from here — so the moment worth catching a broken tree is before the commit, on the
machine, not minutes later in a hosted runner. A hook also keeps the checks runnable with
nothing but a clone and `ruff` installed.

Configuration lives in `pyproject.toml` at the repo root — `[tool.ruff]` only, with no
`[project]` or `[build-system]` table, so it stays tool configuration rather than the
packaging metadata this repo deliberately removed.

The rule selection is pinned explicitly rather than left to ruff's defaults. Those defaults
move between releases: ruff 0.16 began emitting `B` (bugbear) and `I` (import sorting) with
no configuration at all, which would silently change what "passes" means on the next
`yay -Syu`.
