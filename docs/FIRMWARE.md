# Firmware

`firmware/AgentDot/AgentDot.ino` runs on any ESP32 with Wi-Fi: Seeed **XIAO ESP32C3**, **ESP32-C3 SuperMini**, **ESP32-S3 SuperMini** (tested).

## Flash it (Arduino IDE)

1. **Boards Manager**
   1. Add this URL under **Settings → Additional boards manager URLs**:
      ```
      https://espressif.github.io/arduino-esp32/package_esp32_index.json
      ```
   2. In **Boards Manager**, install **esp32 by Espressif Systems**. Not "Arduino ESP32 Boards".
2. **Libraries**: install **Adafruit NeoPixel** (by Adafruit) and **WiFiManager** (by tzapu, 2.0.17 or newer).
3. **Settings** (Tools menu)

   | Setting | XIAO ESP32C3 | ESP32-C3 SuperMini | ESP32-S3 SuperMini |
   |---|---|---|---|
   | Board | **XIAO_ESP32C3** | **ESP32C3 Dev Module** | **ESP32S3 Dev Module** |
   | USB CDC On Boot | **Enabled** | **Enabled** | **Enabled** |
   | Flash Size | 4MB | 4MB | 4MB |
   | Erase All Flash Before Upload | Disabled (keeps your Wi-Fi) | Disabled | Disabled |

4. **Check the top of the sketch** (defaults are fine for the standard build):
   - `LED_PIN`: the pin your strip's DIN is on (default 10 = **D10** on the XIAO).
   - `NUM_LEDS`: 3 (the v12 case uses one pixel: set 1, though 3 also works). `LED_TYPE`: `NEO_GRB` (`NEO_GRBW` for RGBW SK6812).
   - `MAX_BRIGHTNESS`: 90 of 255.
   - Power settings: `CPU_MHZ`, `IDLE_DARK_AFTER_MS`, `DEEP_SLEEP_AFTER_MIN`, `WAKE_PIN` (below).
5. **Upload**: switch Agent Dot **OFF**, plug in the board's USB-C and click Upload. If it says the port is busy or doesn't exist: unplug, hold **BOOT** (**B** on the XIAO) while plugging in, release, re-select the port (its name may change) and upload again. Press **RESET** (**R**) afterwards.

**XIAO ESP32C3: attach the antenna** (the flat one on a wire, onto the U.FL connector) before testing Wi-Fi. The board has no antenna of its own.

### PlatformIO

```bash
cd firmware
pio run -e xiao_esp32c3 -t upload      # or esp32c3_supermini / esp32s3_supermini
pio device monitor
```

`platformio.ini` builds the sketch folder directly; nothing needs renaming.

## Wi-Fi setup (once) – no passwords in the code

1. Switch on. The LEDs show a rainbow, then **blink white**.
2. Join the Wi-Fi network **AgentDot-Setup** from a phone or laptop. The setup page opens; if it doesn't, go to http://192.168.4.1.
3. Tap **Configure WiFi**, pick your network (**2.4 GHz**), enter the password.
4. Optional: fill in **Fixed IP** and **Router / gateway IP** (see below). Save.
5. The LEDs turn **dim teal**: connected. Wi-Fi details are stored in the chip's flash and survive firmware updates.

**If the AgentDot-Setup network never appears**, copy `secrets.example.h` to `secrets.h` next to the sketch, put your network in `WIFI_SSID` / `WIFI_PASS`, and upload again. `secrets.h` is git-ignored, so it never ends up in the repository.

**To change Wi-Fi later**, open `http://<light>/reset-wifi` or type `resetwifi` in the Serial Monitor.

## Finding the light: fixed IP and mDNS

The fastest way to reach the light is a **plain IP address**: no name lookup, and DHCP is skipped when it reconnects. Pick one of:

- **Router reservation** (best): reserve the light's current IP for the device named **agentdot**.
- **Fixed IP in the firmware**: in the setup page, or later with
  ```bash
  curl "http://agentdot.local/staticip?ip=192.168.1.42&gw=192.168.1.1"   # restarts on the new IP
  curl "http://192.168.1.42/staticip?ip=off"                              # back to automatic (DHCP)
  ```
  or in the Serial Monitor: `staticip 192.168.1.42 192.168.1.1`. It assumes a normal home network (`255.255.255.0`); choose an address outside your router's DHCP range.

**mDNS fallback**: the light always answers as `agentdot.local`. The hook script and Mac watcher try the saved IP first and fall back to `agentdot.local` if it fails. On macOS, `dns-sd -G v4 agentdot.local` shows the IP; the Serial Monitor also prints it every 30 s.

## Power and battery

What the firmware does to save power, without changing any colours:

| | |
|---|---|
| CPU at 80 MHz | `CPU_MHZ`, about 10 mA less than 160 MHz; Wi-Fi needs at least 80 |
| CPU idles between loop passes | a 2 ms pause per pass lets the chip sleep instead of spinning |
| Wi-Fi modem sleep | always on; the radio wakes for every beacon, so requests still arrive within ~0.1 s |
| LEDs refreshed only when they change | a dark or steady light costs no CPU time |
| Slower animation when idle | 20 fps for the slow teal breathe, 4 fps once dark, 50 fps for everything else |
| Idle glow goes dark | after `IDLE_DARK_AFTER_MS` (10 min) with no news; any request brings it back |
| Deeper modem sleep when quiet | after the same 10 min the radio switches to `WIFI_PS_MAX_MODEM`; a request still wakes it (about 0.1–0.3 s slower) and it returns to fast mode at once |
| Reduced Wi-Fi transmit power | 8.5 dBm: plenty for a laptop next to a router, and the SuperMini boards need it anyway |

Rough battery life with a 400 mAh cell: about 8–12 hours of normal use on a C3 (an estimate, not yet measured on this firmware). Wi-Fi is most of the draw. Please share measurements in an issue.

### Deep sleep (optional)

`DEEP_SLEEP_AFTER_MIN` puts the chip into deep sleep (~0.05 mA for the chip; the LED strip still draws ~1 mA per LED unless its power is switched) after that many minutes with no news. **In deep sleep the Wi-Fi is off, so a request cannot wake it.** Wake it with the power switch, or wire a push button from `WAKE_PIN` to GND (C3: GPIO 0–5, e.g. XIAO **D1 = GPIO3**; add a 10 kΩ pull-up to 3V3) – it is back on Wi-Fi about 1–2 s later. It is off by default (`0`), because a light that silently stops listening is confusing; turn it on if you often leave it switched on overnight.

## What the firmware does

- **Light states**: off, idle, working, waiting, done, error. The animations are listed in the [README](../README.md).
- **Sessions**: each report can carry a session id. The light shows the highest-priority session: waiting > error > working > done > idle.
  - "done" fades to idle after `DONE_HOLD_MS` (1 minute).
  - A session with no news for `STALE_MS` (30 minutes) is dropped.
  - Requests with a timestamp (`t`) that arrive out of order are ignored.
- **Ways to control it**: a local web page and HTTP API (`/s?c=` fast path), Serial commands, and (optionally) the ntfy.sh relay for cloud agents. See [API.md](API.md).
- **Relay replay**: when the relay connection reopens, the last 10 minutes are replayed with their real age, so the light catches up after a Wi-Fi drop or reboot.
- **SuperMini boards**: Wi-Fi transmit power is lowered, because many of these boards only connect reliably that way.
