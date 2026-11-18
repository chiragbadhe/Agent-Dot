# Troubleshooting

Every problem below came up while building the first Agent Dot.

## Arduino IDE

| Message / symptom | Fix |
|---|---|
| `Platform 'esp32:esp32' not found` | Add the Espressif boards URL and install **esp32 by Espressif Systems** ([FIRMWARE.md](FIRMWARE.md)). |
| `WiFiManager.h: No such file or directory` | Library Manager: install **WiFiManager by tzapu**. Also install **Adafruit NeoPixel**. |
| `This chip is ESP32-S3, not ESP32-C3` | Your board is an S3: choose **ESP32S3 Dev Module**. |
| Serial Monitor says "Not connected" / prints nothing | Set **USB CDC On Boot → Enabled** and upload again. |
| Upload: `Could not open /dev/cu.usbmodem…, the port is busy or doesn't exist` | Put the board in download mode: unplug, hold **BOOT** (**B** on the XIAO), plug in, release. Re-select the port in **Tools → Port** – its name often changes (`ls /dev/cu.*`). Close the Serial Monitor. Use a **data** USB cable straight into the computer. After uploading, press **RESET** (**R**). |
| Board connects and disconnects in a loop | Reboot loop, usually a power dip when Wi-Fi starts. Unplug the battery and LEDs and use a good cable. A brownout message in the Serial Monitor confirms it. Add 10–100 µF across 3V3–GND. |

## LEDs

| Symptom | Fix |
|---|---|
| Strip stays dark | `LED_PIN` doesn't match the wired pin; DIN isn't at the strip's **input** end; no 5V/GND to the strip. |
| Only a small LED on the board blinks | That's the board's charge LED (no battery on its BAT pad). It's harmless and has nothing to do with the strip. |
| Using GPIO12/13 on a C3 crashes it | Those pins belong to the flash memory. Use 4–7 or 10, or set Flash Mode = DIO. |
| Light stuck on one colour | Something reported a state and then stopped (e.g. a relay outage). It clears itself after 30 minutes, or send `idle` (no id) to clear everything. |
| Idle light goes dark | By design: after 10 quiet minutes the teal glow fades out to save battery. Any request brings it back. Change `IDLE_DARK_AFTER_MS` (0 = never). |
| Light dead until switched off and on | Deep sleep is on (`DEEP_SLEEP_AFTER_MIN` > 0): Wi-Fi is off while sleeping. Use the wake button or set it to 0. |

## Wi-Fi and network

| Symptom | Fix |
|---|---|
| No **AgentDot-Setup** network, light is soft blue/teal | It's **already connected** – Wi-Fi details survive uploads, so there's no setup network. Find its IP with `curl http://agentdot.local/status` or the Serial Monitor. Type `resetwifi` in the Serial Monitor to set up a different network. |
| No **AgentDot-Setup** network, light blinks white | XIAO ESP32C3: the **antenna isn't attached** – click it onto the U.FL connector. Otherwise put `WIFI_SSID`/`WIFI_PASS` in `secrets.h` and upload again. |
| `"rssi"` in `/status` is −75 or lower | Weak signal: slower replies, more battery drain. Check the XIAO antenna is clicked on and lies flat, away from the battery and the laptop lid's metal. |
| `agentdot.local` won't resolve / times out | Use the IP (Serial Monitor, `dns-sd -G v4 agentdot.local`, router list). On macOS, allow **Local Network** for your terminal and browser. |
| `zsh: no matches found: http://…?s=working` | Put the URL in quotes. |
| `cp: … is not a directory` when pasting commands | zsh doesn't treat `#` as a comment when you paste; remove inline comments. |
| First request after a long pause is slower | Normal: after 10 quiet minutes the radio uses deeper modem sleep and answers ~0.1–0.3 s later. Following requests are fast again. |
| Lost the light after setting a fixed IP | The address was outside your network or clashed. Type `staticip off` in the Serial Monitor (or hold BOOT and reflash), then pick an address outside the router's DHCP range. |
| Mac and light can't see each other | Both must be on the same network: not a guest network, hotspot or VPN, and the light needs **2.4 GHz**. |

## Claude integrations

| Symptom | Fix |
|---|---|
| `./hooks/install.sh: Operation not permitted` | Run it with bash: `bash hooks/install.sh <ip>` (downloaded files may be quarantined; `xattr -cr <project folder>` clears that). |
| `bash: hooks/install.sh: Operation not permitted` (even with bash) | Your terminal isn't allowed into Downloads/Desktop/Documents. **System Settings → Privacy & Security → Files and Folders** → your terminal → **Downloads Folder** on (or **Full Disk Access**), then **Cmd+Q** the terminal and reopen it. Or move the project out of Downloads. |
| `mac/install.sh`: `Needs the Xcode command line tools` / `swiftc: command not found` | `xcode-select --install`, then run the installer again. |
| Claude Code doesn't change the light | Restart Claude Code; check `/hooks`; run `curl "http://$(cat ~/.agentdot/host)/s?c=working"` by hand; re-run `hooks/install.sh <ip>`. The hook itself is silent by design, so test with curl. |
| Same state not re-sent | Repeats of the same state per session are skipped for 2 minutes. `rm ${TMPDIR:-/tmp}/agentdot-*` resets that. |
| Claude desktop app: light never turns purple | `tail ~/Library/Logs/AgentDotWatch.log`. "waiting for Accessibility permission" → turn on AgentDotWatch in Privacy & Security → Accessibility. Otherwise run `AgentDotWatch --dump` while Claude answers and put the Stop button's label in `~/.agentdot/stop_labels`. |
| Watcher logs "light not reachable" | Allow AgentDotWatch under Privacy & Security → Local Network; check `~/.agentdot/host`. |
| Claude app: green flashes while Claude is still working | Old watcher build. Update the project and run `bash mac/install.sh <ip>` (then redo Accessibility: it rebuilt). The current one waits 2.5 s before "done". |
| Claude app: green instead of amber when Claude asks something | Run `AgentDotWatch --dump \| grep INPUT` while the prompt is open. If its buttons aren't marked INPUT, add their labels to `~/.agentdot/input_labels` and restart the watcher. |
| Watcher stopped working after an update / rebuild | macOS ties the Accessibility permission to the binary. Remove AgentDotWatch from the Accessibility list, add `~/Applications/AgentDotWatch.app` again. |
| Claude app: status line says `cannot reach ntfy.sh` | Turn on **Use the internet while making files** (Settings → Capabilities). |
| Claude app: colours arrive late or not at all | ntfy.sh's free per-IP limits (429 / daily quota). See [CLAUDE_APP.md](CLAUDE_APP.md#limits-read-this). |
