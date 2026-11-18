# Design history

| Version | Change |
|---|---|
| v1 | Landscape electronics box, separate clip |
| v2 | Portrait box hidden behind the screen, slide-in diffuser strip, enclosed wire path |
| v3 | Clip and box merged into one body; stronger LED cap and cover |
| v4–v5 | 60 mm LED box for a 10/12 mm strip; LED box screwed to the body; open-bottom box with a flanged cover (no unsupported overhangs) |
| v6 | 60 mm clamp plate, fingers at the corners, bigger window |
| v7 | Clamp moved onto the LED unit (clips on by itself); controller box screws to its jaw; flush 45° seat |
| v8 | Slim 1.6 mm back wall (9.6 mm behind the lid); joint screws from the lid side; strip slot + end plug |
| v9 | 5 mm low-profile LED box: strip flat on the floor, reflector roof, front diffuser |
| v10 | 8 mm tall, 32 mm wide LED unit (same width as the controller box) |
| v11 | 6 mm tall, 32 mm wide; LED box floor is the clamp plate (6.8 mm above the lid) |
| **v12** | **One-piece body** (LED box + clamp + controller box) + cover; ESP32 SuperMini + **TP4056 USB-C slot**; one RGB pixel at the back of the LED box; both USB-C ports in the side wall. v1–v11 files removed from the repo. |
| firmware | Wi-Fi setup portal, HTTP/Serial API, Claude Code hooks, ntfy.sh relay for the Claude app, per-session states with priorities, replay after reconnect |
| firmware 2 | Efficiency pass, same colours: `/s?c=` fast endpoint, 80 MHz CPU, redraw only on change, idle dark + deeper modem sleep after 10 min, optional deep sleep, fixed IP (setup page / `/staticip` / serial), out-of-order protection (`t`), secrets in git-ignored `secrets.h`, PlatformIO envs for XIAO ESP32C3 |
| integrations 2 | Non-blocking background hook (returns in ~15 ms, dedupes PreToolUse, filters idle reminders), PostToolUse, saved IP + mDNS fallback; `hooks/` replaces `integrations/claude-code/`; new `mac/` Accessibility watcher for the Claude desktop app with launchd setup |
| docs 2 | `docs/INSTALL.md` step-by-step setup guide; installers run with `bash`; troubleshooting for upload port, Downloads permission, XIAO antenna, Accessibility after rebuilds. Watcher: amber for permission prompts / questions, 2.5 s "done" delay, no rebuild when unchanged |
