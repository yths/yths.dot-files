# Packages

Third-party packages whose AUR build is broken, each carried here as the AUR `PKGBUILD` with
the fix applied. `./bootstrap.sh` builds every `packages/<pkgname>/` that `pacman -Q
<pkgname>` does not already know, in a scratch directory with `makepkg -si`, right after the
`[packages]` groups from `setup.toml` -- so none of these is listed there as well.

The directory name is the package name. The bootstrap relies on that to skip what is
installed, and `tests/test_setup.py` checks it against the `pkgname` the PKGBUILD declares.
Each PKGBUILD's header says what was changed and why, so the fix can be dropped when the AUR
catches up: delete the directory and put the name back in `setup.toml`.

| Package | What is fixed |
|---|---|
| `nody-greeter` | The web-greeter runtime LightDM renders the login screen with. `package.patch` replaces the electron rebuild step and allows the two install scripts npm now refuses by default; without it the native `node-gtk` module never builds. |
| `python-colour-science` | Perceptual colour matching for `helper/color_match.py`. `openimageio` is made a hard dependency -- `colour` imports it when present and the AUR package only comments it out -- and `check()` also skips `test_write_spectral_image_Fichet2021`, which fails against the current `openimageio`. |

By hand, for one of them:

```bash
build_directory="$(mktemp -d)"
cp -R packages/<pkgname>/. "$build_directory"
(cd "$build_directory" && makepkg -si)
rm -rf "$build_directory"
```
