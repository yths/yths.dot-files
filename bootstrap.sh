#!/usr/bin/env bash
# Install this desktop on a fresh Arch system, in one command.
#
#     ./bootstrap.sh                  from a clone
#     ./bootstrap.sh --dev            also install pytest and test tools, for changing the repository
#     ./bootstrap.sh --dry-run        print what would happen and stop
#     ./bootstrap.sh --skip-system    leave the boot splash and login screen alone
#
# From a console on a machine that has nothing yet, it is the whole install: packages, the
# ones under packages/ that the AUR cannot build, the services, the configuration, the login
# screen. Reboot when it is done. It asks
# for the sudo password, and install.py asks once whether to collect credentials; that is all
# the typing. The boot splash wants two edits to files that decide whether the machine boots,
# so that one is left for later and said so at the end.
#
# Everything it installs comes from setup.toml. Edit that first if you want a different
# theme, fallback font, or package set; nothing needs editing here.
#
# Safe to re-run: yay skips what is present, and install.py backs up whatever it replaces.

set -euo pipefail

REPOSITORY_URL="https://github.com/yths/yths.dot-files.git"
BACKEND_URL="https://github.com/yths/yths.backend-service.git"
DEFAULT_CLONE_PATH="$HOME/repositories/yths.dot-files"

dry_run=false
development=false
system=true
for argument in "$@"; do
    case "$argument" in
        --dry-run) dry_run=true ;;
        --dev) development=true ;;
        --skip-system) system=false ;;
        -h|--help) sed -n '2,19p' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) printf 'unknown option: %s\n' "$argument" >&2; exit 2 ;;
    esac
done

say() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
run() { if $dry_run; then printf '    would run: %s\n' "$*"; else "$@"; fi; }

# --- refuse the machines this cannot work on, before changing anything -------------------
if [ "$(id -u)" -eq 0 ]; then
    printf 'Run this as your own user, not root. It installs into your home directory,\n' >&2
    printf 'and calls sudo only where a package or a system path needs it.\n' >&2
    exit 1
fi
if ! command -v pacman >/dev/null 2>&1; then
    printf 'This installs an Arch Linux desktop and needs pacman. See docs/os-build.md for\n' >&2
    printf 'getting to a bootable Arch system first.\n' >&2
    exit 1
fi

# --- locate the repository: the clone we are in, or one we make --------------------------
if [ -f "$(dirname "$(readlink -f "$0")")/setup.toml" ]; then
    REPOSITORY_PATH="$(dirname "$(readlink -f "$0")")"
    say "Using this clone: $REPOSITORY_PATH"
else
    REPOSITORY_PATH="${DOTFILES_REPOSITORY_PATH:-$DEFAULT_CLONE_PATH}"
    if [ -d "$REPOSITORY_PATH/.git" ]; then
        say "Updating $REPOSITORY_PATH"
        run git -C "$REPOSITORY_PATH" pull --ff-only
    else
        say "Cloning into $REPOSITORY_PATH"
        run mkdir -p "$(dirname "$REPOSITORY_PATH")"
        run git clone "$REPOSITORY_URL" "$REPOSITORY_PATH"
    fi
fi

# --- the AUR helper, which some of the packages need -------------------------------------
if ! command -v yay >/dev/null 2>&1; then
    say "Installing yay"
    run sudo pacman -S --needed --noconfirm git base-devel
    build_directory="$(mktemp -d)"
    run git clone https://aur.archlinux.org/yay.git "$build_directory/yay"
    if ! $dry_run; then (cd "$build_directory/yay" && makepkg -si --noconfirm); fi
    run rm -rf "$build_directory"
fi

# --- packages, read from setup.toml so this script holds no list of its own --------------
# The fallback font goes in with them: it has to be on the machine before the theme's own
# font is attempted below, so that attempt failing leaves a desktop that still renders.
groups="core boot backend python optional"
$development && groups="$groups development"
packages="$(python - "$REPOSITORY_PATH/setup.toml" $groups <<'PYEOF'
import sys, tomllib
with open(sys.argv[1], "rb") as handle:
    setup = tomllib.load(handle)
names = [setup["desktop"]["fallback_font_package"]]
names += [name for group in sys.argv[2:] for name in setup["packages"].get(group, [])]
print(" ".join(dict.fromkeys(names)))
PYEOF
)"
say "Installing $(printf '%s' "$packages" | wc -w) packages"
# shellcheck disable=SC2086 -- the list is deliberately word-split into arguments.
run yay -S --needed --noconfirm $packages

# --- the packages this repository builds itself ---------------------------------------------
# packages/<pkgname>/PKGBUILD, one directory per package whose AUR build is broken: nody-greeter
# (the electron rebuild step and npm's script allow-list) and python-colour-science (a test that
# fails against current openimageio, and openimageio itself left out of depends). Each is the
# AUR PKGBUILD with the fix applied; the header of each says what. Built in a scratch directory
# so makepkg's src/ and pkg/ never land in the clone, with -s for the make dependencies, and
# skipped once installed -- nody-greeter is minutes of npm. Before the import check below,
# because python-colour-science is one of the imports it checks.
for package_directory in "$REPOSITORY_PATH"/packages/*/; do
    package_name="$(basename "$package_directory")"
    if pacman -Q "$package_name" >/dev/null 2>&1; then
        continue
    fi
    say "Building $package_name from packages/$package_name"
    build_directory="$(mktemp -d)"
    run cp -R "$package_directory." "$build_directory"
    if ! $dry_run; then (cd "$build_directory" && makepkg -si --needed --noconfirm); fi
    run rm -rf "$build_directory"
done

# --- is this python the one those packages landed in? -------------------------------------
# install.py imports cairo, PIL, numpy and the rest through the helpers, and a missing one
# surfaced as an ImportError from inside the orchestrator with the real cause two tracebacks
# up. A virtualenv or pyenv shim on PATH, or a yay run that was interrupted, are the ways the
# packages above end up somewhere other than where `python` looks.
say "Checking that $(command -v python) can import what was just installed"
if ! run python "$REPOSITORY_PATH/helper/list_dependencies.py" --missing; then
    printf '\n%s\n' "The packages are installed, but not for this python. Make sure \`python\` is" >&2
    printf '%s\n' "/usr/bin/python (deactivate any virtualenv), or install the ones named above." >&2
    exit 1
fi

# --- the theme's font, which the theme decides and this machine may not be able to get -----
# helper/fonts.py reads the configured theme's bundle and says which package provides its
# family; nothing when setup.toml leaves the theme to the prompt, or the family is one it has
# no package for. A failure here is reported and not fatal: install.py sees the family is
# missing and writes the fallback into the configuration instead.
theme_font="$(python "$REPOSITORY_PATH/helper/fonts.py" --package 2>/dev/null || true)"
if [ -n "$theme_font" ]; then
    say "Installing the theme's font: $theme_font"
    run yay -S --needed --noconfirm "$theme_font" \
        || printf 'Could not install %s; the desktop falls back to the font in setup.toml.\n' "$theme_font" >&2
fi

say "Enabling PipeWire audio"
run systemctl --user enable --now pipewire.socket pipewire-pulse.socket wireplumber.service \
    || printf 'Could not enable PipeWire audio; retry from a logged-in user session.\n' >&2
run pactl info \
    || printf 'Could not contact the audio server; check PipeWire after logging in.\n' >&2

# --- the services the bar reads from -------------------------------------------------------
# valkey is the store; the backend service, its own repository, is what writes into it. Both
# are enabled now so the bar has numbers at the first login. The backend is a user unit, so no
# root; a failure here costs the bar its metrics and nothing else, hence not fatal.
say "Enabling valkey"
run sudo systemctl enable --now valkey.service

backend_path="$(dirname "$REPOSITORY_PATH")/yths.backend-service"
if [ -d "$backend_path/.git" ]; then
    say "Updating the backend service in $backend_path"
    run git -C "$backend_path" pull --ff-only || true
else
    say "Cloning the backend service into $backend_path"
    run git clone "$BACKEND_URL" "$backend_path" || true
fi
if [ -f "$backend_path/backend.service" ]; then
    run mkdir -p "$HOME/.local/share/systemd/user"
    run cp "$backend_path/backend.service" "$HOME/.local/share/systemd/user/"
    run systemctl --user daemon-reload || true
    run systemctl --user enable --now backend.service \
        || printf 'Could not enable the backend service; the bar runs without its metrics.\n' >&2
else
    printf 'No backend.service in %s; the bar runs without its metrics.\n' "$backend_path" >&2
fi

if $dry_run || [[ -f "$backend_path/pacman_post_transaction.py" &&
    -f "$backend_path/update_count.py" && -f "$backend_path/subprocess_safe.py" &&
    -f "$backend_path/redis-updates.hook" ]]; then
    say "Installing the package-update hook"
    run sudo install -d -m 755 /usr/local/bin /etc/pacman.d/hooks &&
        run sudo install -m 755 "$backend_path/pacman_post_transaction.py" \
            /usr/local/bin/pacman-redis-updates &&
        run sudo install -m 644 "$backend_path/update_count.py" \
            /usr/local/bin/update_count.py &&
        run sudo install -m 644 "$backend_path/subprocess_safe.py" \
            /usr/local/bin/subprocess_safe.py &&
        run sudo install -m 644 "$backend_path/redis-updates.hook" \
            /etc/pacman.d/hooks/redis-updates.hook \
        || printf 'Could not install the package-update hook; updates refresh hourly.\n' >&2
else
    printf 'Backend hook files are missing in %s; updates refresh hourly.\n' "$backend_path" >&2
fi

# --- the dot files, and with --system the two that write outside $HOME ---------------------
# install.py --system asks for root once, before it changes anything, and installs the login
# screen and boot splash last: everything before them is reversible by re-running, while they
# change how the machine boots and logs in. The login screen installer also points LightDM at
# nody-greeter and enables the service -- enabled, not started, so this console stays yours
# until the reboot. --skip-system leaves all of it.
if $system; then
    say "Installing the configuration, the login screen and the boot splash"
    run python "$REPOSITORY_PATH/install.py" --system
else
    say "Installing the configuration (--skip-system: no login screen or boot splash)"
    run python "$REPOSITORY_PATH/install.py"
fi

say "Done"
cat <<'EOF'
    Reboot into the login screen, or `startx` from here to look first.

    Left for later, from the desktop -- none of it is needed to log in:
      - the boot splash: add `plymouth` to HOOKS in /etc/mkinitcpio.conf and `splash` to the
        kernel command line, then `python install.py --migrate --system`
      - display calibration, credentials, a different theme: docs/install.md
EOF
