# Dot Files

Configuration files, theme presets, and patches for an Arch Linux desktop built around qtile, web-greeter, plymouth, and a Redis-backed system metrics service. Theme presets ship under `assets/`; additional themes can be exported there by the [yths.themes](https://github.com/yths/yths.themes) orchestrator.

## Getting Started

Clone this repository and run the installer on a machine that already runs Arch Linux; the full walkthrough is in [docs/install.md](docs/install.md). To build that machine from a blank disk first, see [docs/os-build.md](docs/os-build.md).

```bash
git clone https://github.com/yths/yths.dot-files.git
cd yths.dot-files
python install.py
```

## Dependencies

- [IPinfo](https://ipinfo.io/) — an API access token is required to translate the external IP into geolocation data, used to determine sunrise/sunset times for the automated dark/light theme switch.
- [yths.backend-service](https://github.com/yths/yths.backend-service) — publishes the Redis streams the qtile widgets subscribe to.

## Documentation

- [docs/install.md](docs/install.md) — installing this desktop on an existing Arch system, through display calibration
- [docs/os-build.md](docs/os-build.md) — building the base Arch system from a blank disk (optional background)
- [docs/architecture.md](docs/architecture.md) — whole-system overview: theme bundles, installer flow, patchers, widgets, backend contract
- [docs/notes.md](docs/notes.md) — theme system, qtile widget architecture, yths.themes contract, palette design
- [docs/config-schema.md](docs/config-schema.md) — `~/.config/config.json` schema
- [docs/palette-semantics.md](docs/palette-semantics.md) — what each palette token *means*, and the contract every preset must honour
- [docs/palette-reference.md](docs/palette-reference.md) — generated: *where* each token is used, per app, and which tools still hardcode hex
- [docs/palettes/](docs/palettes/) — what each token *looks like*, one swatch reference per bundled preset
- [docs/keybindings.md](docs/keybindings.md) — generated overview of every keyboard binding, grouped by tool
- [docs/dependencies.md](docs/dependencies.md) — Python imports mapped to Arch packages, development tooling, and the pre-commit gate
- [docs/tips.md](docs/tips.md) — recipes for theme switching, previewing, debugging
- [docs/issues.md](docs/issues.md) — known issues and roadmap
- [docs/style.md](docs/style.md) — documentation style guide (for contributors)

Changing anything here: [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE.md).
