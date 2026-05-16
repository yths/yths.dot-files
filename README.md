# Dot Files

Configuration files, theme presets, and patches for an Arch Linux desktop built around qtile, web-greeter, plymouth, and a Redis-backed system metrics service. Two color/theme presets ship by default — `yths` and `nuunamnir` — and additional themes can be exported into `assets/` by the [yths.themes](https://github.com/yths/yths.themes) orchestrator.

## Getting Started

Clone this repository and run the installer; full setup including the base OS lives in [docs/install.md](docs/install.md).

```bash
git clone https://github.com/yths/yths.dot-files.git
cd yths.dot-files
python install.py
```

## Dependencies

* [IPinfo](https://ipinfo.io/) — an API access token is required to translate the external IP into geolocation data, used to determine sunrise/sunset times for the automated dark/light theme switch.
* [yths.backend-service](https://github.com/yths/yths.backend-service) — publishes the Redis streams the qtile widgets subscribe to.

## Documentation

* [docs/install.md](docs/install.md) — full installation walkthrough, from base Arch through display calibration
* [docs/notes.md](docs/notes.md) — theme system, color schemes, qtile widget architecture, yths.themes contract
* [docs/tips.md](docs/tips.md) — recipes for theme switching, previewing, debugging
* [docs/issues.md](docs/issues.md) — known issues and roadmap
