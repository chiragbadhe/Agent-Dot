# Contributing

Ideas, fixes and photos of your build are all welcome.

- **Bugs / questions**: open an issue. Say which board, laptop (lid thickness) and firmware you used.
- **CAD changes**: edit `hardware/cad/agent_dot.FCMacro` or `hardware/cad/v12.py`, then run `validate_v12.py` and attach the report. All checks must pass. Regenerate the print files with `export_v12.py`, `make_3mf_v12.py` and `render_v12.py` (see [docs/CAD.md](docs/CAD.md)).
- **Firmware**: keep the command set in [docs/API.md](docs/API.md) backwards compatible, and update the docs when it changes.
- **New integrations** (other agents, editors, CI): anything that can send an HTTP request or publish to the relay works. Add it under `integrations/` with a short doc (Claude Code hooks live in `hooks/`, the Mac watcher in `mac/`).
- **Never commit** Wi-Fi passwords, relay topics or access tokens.

Wanted:

- tested `LAPTOP_T` values for MacBook Airs and other laptops
- an MQTT / self-hosted relay option
- battery-life measurements for the XIAO ESP32C3 and C3 SuperMini
