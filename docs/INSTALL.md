# Setup guide: from a flashed board to a working light

This is the whole software setup, in order, as it was done on the first build (MacBook, macOS). The v12 case holds an **ESP32 SuperMini**; the steps are the same for a XIAO ESP32C3 on the bench. Each step only depends on the one before it, so if something fails, fix that step before moving on. Wiring and printing are covered in [WIRING.md](WIRING.md) and [PRINTING.md](PRINTING.md).

**What you end up with**

| Claude is… | Claude Code | Claude desktop app | Light |
|---|---|---|---|
| working / answering | hooks | AgentDotWatch | purple sweep |
| asking you something (permission, question) | hooks | AgentDotWatch | amber pulse |
| finished | hooks | AgentDotWatch | green, then dim teal after a minute |

Total time: about 20 minutes.

---

## 0. Before you start

- **Antenna (XIAO ESP32C3)**: the XIAO has no antenna on the board. Click the supplied flat antenna onto the small gold U.FL connector before anything else. Without it the light can't be seen on Wi-Fi at all. Keep the antenna flat and away from the battery. `/status` shows the signal as `rssi`: −40 to −65 is good, −75 or lower is weak.
- **Where the project lives**: macOS protects `~/Downloads`, `~/Desktop` and `~/Documents`. If your terminal app hasn't been allowed into that folder, every script fails with `Operation not permitted`. Either:
  - give your terminal access: **System Settings → Privacy & Security → Files and Folders** → your terminal → **Downloads Folder** on (or add it under **Full Disk Access**), then quit the terminal with **Cmd+Q** and reopen it; or
  - move the project folder somewhere unprotected, e.g. `~/agent-dot`.
- **Run the installers with `bash`**: files from a download may carry a quarantine flag that stops them running directly (`./install.sh` → `Operation not permitted`). `bash hooks/install.sh` always works. To clear the flag for the whole folder: `xattr -cr ~/Downloads/"agent-dot 2"`.

In the commands below, replace the folder path with yours and `192.168.1.55` with your light's IP.

---

## 1. Flash the firmware

Full details and board settings: [FIRMWARE.md](FIRMWARE.md).

1. Arduino IDE: install **esp32 by Espressif Systems** (Boards Manager), **Adafruit NeoPixel** and **WiFiManager by tzapu** (Library Manager).
2. **Tools → Board**: **ESP32C3 Dev Module** or **ESP32S3 Dev Module** for the SuperMini (whatever its chip says), **XIAO_ESP32C3** for a XIAO. **USB CDC On Boot → Enabled**.
3. Open `firmware/AgentDot/AgentDot.ino` (for the v12 case you can set `NUM_LEDS 1`). Switch the Dot's power switch **off** and plug the board into the Mac (in the v12 case: the **lower** USB-C).
4. Click **Upload**.

**If the upload fails with `Could not open /dev/cu.usbmodem…, the port is busy or doesn't exist`**, the board isn't in download mode:

1. Unplug the USB cable.
2. Hold the **B** (BOOT) button, plug the cable in, release B.
3. **Tools → Port**: pick the port again. Its name often changes after replugging (`ls /dev/cu.*` lists them).
4. Close the Serial Monitor if it's open, then **Upload** again.
5. After "Hard resetting…", press **R** (RESET) once to start the new firmware.

Still failing: try another USB-C cable (many are charge-only) plugged straight into the Mac.

PlatformIO instead: `cd firmware && pio run -e esp32c3_supermini -t upload` (or `esp32s3_supermini`, `xiao_esp32c3`).

---

## 2. Join Wi-Fi

1. Press **R** and open the Serial Monitor at **115200** baud.
2. Read the light:
   - **rainbow, then blinking white** → it needs Wi-Fi. Join **AgentDot-Setup** from your phone, open http://192.168.4.1 if the page doesn't appear, pick your **2.4 GHz** network, enter the password, save.
   - **soft blue/teal breathing** → it is **already on Wi-Fi** (Wi-Fi details survive uploads). There's no setup network in this case. That's normal; skip to step 3.
3. The Serial Monitor prints the address every 30 s: `[agentdot] http://192.168.1.55  (http://agentdot.local)`. Or run `curl http://agentdot.local/status` and look at `"ip"`.

To join a different network later, type `resetwifi` in the Serial Monitor (line ending: Newline).

If the setup network never appears and the light blinks white: check the antenna, or put the network in `firmware/AgentDot/secrets.h` (copy `secrets.example.h`) and upload again.

---

## 3. Fix the IP address

Hooks and the watcher talk to a plain IP, which is faster than `agentdot.local`. Make sure it never changes:

```bash
curl "http://192.168.1.55/staticip?ip=192.168.1.55&gw=192.168.1.1"   # your router's IP as gw
```

The light restarts on that address within a few seconds (`"fixed_ip":true` in `/status`). Reserving the address in your router works just as well. Undo with `curl "http://192.168.1.55/staticip?ip=off"`.

---

## 4. Test the light on its own

```bash
IP=192.168.1.55
curl "http://$IP/s?c=working"   # purple sweep
curl "http://$IP/s?c=input"     # amber pulse
curl "http://$IP/s?c=done"      # green flashes, then green
curl "http://$IP/s?c=error"     # red
curl "http://$IP/s?c=idle"      # dim teal
curl "http://$IP/status"        # JSON: state, ip, rssi, fixed_ip, cpu_mhz, uptime
```

Every command should answer `ok` immediately and the light should follow. If not, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md#wi-fi-and-network) before going further.

---

## 5. Claude Code hooks

```bash
cd ~/Downloads/"agent-dot 2"
bash hooks/install.sh 192.168.1.55
```

Expected output:

```
Agent Dot hooks added to /Users/<you>/.claude/settings.json - restart Claude Code (or type /hooks to check).
Sent 'working' - the light should show the purple sweep. Sending 'idle' in 3 s...
```

What it did: copied the hook to `~/.agentdot/agentdot.sh`, saved the IP in `~/.agentdot/host`, backed up `~/.claude/settings.json` to `settings.json.bak` and added the hooks (your other settings are kept).

**Test**: restart Claude Code and send a prompt. Purple while it works, green when it's done. Ask for something that needs approval ("create a file test.txt"): amber while it waits for you, purple again after you approve.

Remove: `bash hooks/install.sh --uninstall`. Details: [CLAUDE_CODE.md](CLAUDE_CODE.md).

---

## 6. Claude desktop app: AgentDotWatch

AgentDotWatch is a small background program for the Mac. It watches the Claude app through the macOS Accessibility API: Stop button visible → purple; Allow / Deny / Submit / Skip prompt visible → amber; both gone for 2.5 s → green.

### 6.1 Build and install

It's built on your Mac from `mac/AgentDotWatch.swift`, so you need Apple's command line tools once:

```bash
xcode-select --install          # skip if already installed ("command line tools are already installed")
```

Then:

```bash
cd ~/Downloads/"agent-dot 2"
bash mac/install.sh 192.168.1.55
```

What `install.sh` does:

1. **Builds** the watcher with `swiftc -O` into `~/Applications/AgentDotWatch.app` – a background-only app (no Dock icon) so the permission prompts show a proper name.
2. **Signs** it locally (ad-hoc) so macOS can track its permissions.
3. **Installs a launchd agent**, `~/Library/LaunchAgents/com.agentdot.watch.plist`, which starts the watcher now, at every login, and again if it ever exits.
4. **Skips the rebuild** when `AgentDotWatch.swift` hasn't changed since the last install, so re-running it doesn't cost you the permissions below.

Expected output ends with `AgentDotWatch is running and will start at every login.`

### 6.2 Grant the permissions (once)

1. **Accessibility** – **System Settings → Privacy & Security → Accessibility**. If **AgentDotWatch** is listed, switch it on. If not: click **+**, press **Cmd+Shift+G**, type `~/Applications/AgentDotWatch.app`, **Open**, switch it on. The watcher notices within a second; no restart needed.
2. **Local Network** – click **Allow** when macOS asks whether AgentDotWatch may find devices on your network. (Check later under **Privacy & Security → Local Network**.)

> **After every rebuild** (only when `AgentDotWatch.swift` changed), macOS treats the watcher as a new app and silently stops trusting it – switching the old entry off and on is not enough. Select **AgentDotWatch** in the Accessibility list, click **−**, then add it again with **+**. The log shows `waiting for Accessibility permission` until you do.

### 6.3 Check it

```bash
tail -f ~/Library/Logs/AgentDotWatch.log
```

Send a message in the Claude app. A healthy log looks like this:

```
started - light at 192.168.1.55
watching Claude (pid 22443), light at 192.168.1.55
-> working          Claude starts answering
-> waiting          Claude asks you something (permission prompt / question)
-> working          you answered, Claude continues
-> done             Claude finished
```

To see which buttons the watcher recognises, run this while Claude is answering or while a prompt is open:

```bash
~/Applications/AgentDotWatch.app/Contents/MacOS/AgentDotWatch --dump | grep -E "STOP|SEND|INPUT"
```

If an app update renames a button, put the new label in `~/.agentdot/stop_labels` or `~/.agentdot/input_labels` (comma-separated) and restart the watcher: `launchctl kickstart -k gui/$(id -u)/com.agentdot.watch`.

Remove: `bash mac/install.sh --uninstall`. Details and the fallback options: [CLAUDE_APP.md](CLAUDE_APP.md).

---

## 7. Done – quick reference

| Task | Command |
|---|---|
| Light status | `curl http://192.168.1.55/status` |
| Set a colour by hand | `curl "http://192.168.1.55/s?c=working"` (`input`, `done`, `error`, `idle`, `off`) |
| Reinstall / update hooks | `bash hooks/install.sh 192.168.1.55` |
| Reinstall / update the watcher | `bash mac/install.sh 192.168.1.55` (then redo Accessibility if it rebuilt) |
| Watcher log | `tail -f ~/Library/Logs/AgentDotWatch.log` |
| Restart the watcher | `launchctl kickstart -k gui/$(id -u)/com.agentdot.watch` |
| Change Wi-Fi | `resetwifi` in the Serial Monitor |
| Remove everything on the Mac | `bash hooks/install.sh --uninstall && bash mac/install.sh --uninstall` |
