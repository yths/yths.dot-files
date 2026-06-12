# Dot Files

Configuration files, theme presets, and patches for an Arch Linux desktop built around qtile, web-greeter, plymouth, and a Redis-backed system metrics service. Theme presets ship under `assets/`; additional themes can be exported there by the [yths.themes](https://github.com/yths/yths.themes) orchestrator.

## Getting Started

Clone this repository and run the installer; full setup including the base OS lives in [docs/install.md](docs/install.md).

```bash
git clone https://github.com/yths/yths.dot-files.git
cd yths.dot-files
python install.py
```

## Dependencies

- [IPinfo](https://ipinfo.io/) — an API access token is required to translate the external IP into geolocation data, used to determine sunrise/sunset times for the automated dark/light theme switch.
- [yths.backend-service](https://github.com/yths/yths.backend-service) — publishes the Redis streams the qtile widgets subscribe to.

## Documentation

- [docs/install.md](docs/install.md) — full installation walkthrough, from base Arch through display calibration
- [docs/architecture.md](docs/architecture.md) — whole-system overview: theme bundles, installer flow, patchers, widgets, backend contract
- [docs/notes.md](docs/notes.md) — theme system, qtile widget architecture, yths.themes contract, color schemes
- [docs/config-schema.md](docs/config-schema.md) — `~/.config/config.json` schema
- [docs/color-semantics.md](docs/color-semantics.md) — what each semantic palette token means
- [docs/colors.md](docs/colors.md) — generated map of palette tokens, per-app role maps, and hardcoded-hex drift
- [docs/keybindings.md](docs/keybindings.md) — generated overview of every keyboard binding, grouped by tool
- [docs/dependencies.md](docs/dependencies.md) — Python imports mapped to Arch packages
- [docs/tips.md](docs/tips.md) — recipes for theme switching, previewing, debugging
- [docs/issues.md](docs/issues.md) — known issues and roadmap
- [docs/style.md](docs/style.md) — documentation style guide (for contributors)

## License

[MIT](LICENSE.md).
