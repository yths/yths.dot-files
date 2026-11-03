#!/usr/bin/env bash
# Install this desktop on a fresh Arch system, in one command.
#
#     ./bootstrap.sh                  from a clone
#     ./bootstrap.sh --dev            also install ruff and pytest, for changing the repository
#     ./bootstrap.sh --dry-run        print what would happen and stop
#     ./bootstrap.sh --skip-system    leave the boot splash and login screen alone
#
# Everything it installs comes from setup.toml. Edit that first if you want a different
# theme, fallback font, or package set; nothing needs editing here.
#
# Safe to re-run: yay skips what is present, and install.py backs up whatever it replaces.

set -euo pipefail

REPOSITORY_URL="https://github.com/yths/yths.dot-files.git"
DEFAULT_CLONE_PATH="$HOME/repositories/yths.dot-files"

dry_run=false
development=false
system=true
for argument in "$@"; do
    case "$argument" in
        --dry-run) dry_run=true ;;
        --dev) development=true ;;
        --skip-system) system=false ;;
        -h|--help) sed -n '2,12p' "$0" | sed 's/^# \?//'; exit 0 ;;
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

# --- the greeter, from this repository's PKGBUILD rather than the AUR ----------------------
# configuration/web-greeter/nody-greeter/ is the AUR package with package.patch applied: the
# upstream electron rebuild step and npm's script allow-list stop the native module building
# otherwise. lightdm, which it depends on, is in the boot group above; makepkg -s fetches the
# make dependencies. Built in a scratch directory so makepkg's src/ and pkg/ never land in the
# clone, and skipped once installed, since the build is minutes of npm.
if ! pacman -Q nody-greeter >/dev/null 2>&1; then
    say "Building nody-greeter from configuration/web-greeter/nody-greeter"
    build_directory="$(mktemp -d)"
    run cp -R "$REPOSITORY_PATH/configuration/web-greeter/nody-greeter/." "$build_directory"
    if ! $dry_run; then (cd "$build_directory" && makepkg -si --needed --noconfirm); fi
    run rm -rf "$build_directory"
fi

# --- the dot files, and with --system the two that write outside $HOME ---------------------
# install.py --system asks for root once, before it changes anything, and installs the login
# screen and boot splash last: everything before them is reversible by re-running, while they
# change how the machine boots and logs in. --skip-system leaves both.
if $system; then
    say "Installing the configuration, the login screen and the boot splash"
    run python "$REPOSITORY_PATH/install.py" --system
else
    say "Installing the configuration (--skip-system: no login screen or boot splash)"
    run python "$REPOSITORY_PATH/install.py"
fi

say "Done"
cat <<'EOF'
    Start the desktop with `startx`, or reboot into the display manager.

    To install the login screen and boot splash later, or again:
      python install.py --migrate --system

    docs/install.md has what they change and why.
EOF
