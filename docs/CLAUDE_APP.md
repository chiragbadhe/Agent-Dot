# Claude desktop app integration

There are two ways to make the light follow the Claude desktop app (chat):

| | **Mac watcher** (recommended) | ntfy.sh relay plugin |
|---|---|---|
| How | watches the app on your Mac via Accessibility | the app publishes to a cloud relay the light listens to |
| Delay | ~0.2–0.4 s | ~1 s, longer when the relay is busy |
| States | working, waiting, done | working, waiting, done, error |
| Limits | none | free relay: per-IP rate limits and a daily quota |
| Needs | macOS, Accessibility permission | `CLOUD_TOPIC` in the firmware, internet access for the app |

## Mac watcher (AgentDotWatch)

`mac/AgentDotWatch.swift` is a small background program. While Claude is answering, the chat shows a **Stop** button; the watcher sends `working` when that button appears and `done` when it disappears. When Claude asks you something instead – a permission prompt (Allow / Deny) or a question (Submit / Skip) – it sends `waiting`, so the light turns **amber** rather than green. It only sends on changes.

It is light on CPU: the first scan finds the message box, and after that it re-checks only that small part of the window every 200 ms. A full window scan runs at most every 3 s (every 1 s while Claude is answering). It checks for prompts right when the Stop button goes away, every second while it's waiting on you, and every 2 s while Claude is answering. Claude briefly hides the Stop button between steps and right after you answer a prompt, so "done" is only sent once nothing has shown for 2.5 s – no green flashes in the middle of a task. When you answer a prompt, the light goes straight back to purple and waits up to 20 s for Claude to continue. Each state is sent to the saved IP, retried once, then tried at `agentdot.local`, so a weak Wi-Fi signal doesn't leave the light on the wrong colour. It also re-sends the state every 5 minutes during very long answers, so the light doesn't drop the session.

### Install

The watcher is compiled on your Mac, so it needs Apple's command line tools once:

```bash
xcode-select --install            # skip if already installed
```

Then build, install and start it:

```bash
cd ~/Downloads/"agent-dot 2"      # wherever the project is
bash mac/install.sh 192.168.1.42  # your light's IP; without it, uses ~/.agentdot/host or agentdot.local
```

`install.sh` does four things:

1. **Builds** `mac/AgentDotWatch.swift` with `swiftc -O` into `~/Applications/AgentDotWatch.app`, a background-only app (no Dock icon), so the permission prompts show a proper name.
2. **Signs** it locally (ad-hoc), so macOS can keep track of its permissions.
3. **Installs and starts a launchd agent**, `~/Library/LaunchAgents/com.agentdot.watch.plist`: it runs now, at every login, and is restarted if it ever exits. Its log goes to `~/Library/Logs/AgentDotWatch.log`.
4. **Skips the rebuild** if `AgentDotWatch.swift` hasn't changed since the last install, so running it again doesn't cost you the Accessibility permission.

The full walkthrough with expected output is in [INSTALL.md, step 6](INSTALL.md#6-claude-desktop-app-agentdotwatch).

### Permissions (once)

1. **Accessibility** – macOS asks the first time. If not: **System Settings → Privacy & Security → Accessibility**, click **+**, choose `~/Applications/AgentDotWatch.app`, turn it on. The watcher notices within a second; no restart needed.
2. **Local Network** – allow it when macOS asks. If requests never reach the light, check **System Settings → Privacy & Security → Local Network**.

**After a rebuild** (when `AgentDotWatch.swift` changed), macOS treats the watcher as a new app and silently stops trusting it. Turning the old entry off and on is **not** enough: select **AgentDotWatch** in the Accessibility list, click **−**, then add `~/Applications/AgentDotWatch.app` again with **+**. Until you do, the log says `waiting for Accessibility permission` and the light doesn't follow the app.

### Check it

```bash
tail -f ~/Library/Logs/AgentDotWatch.log
```

A healthy log:

```
started - light at 192.168.1.55
watching Claude (pid 22443), light at 192.168.1.55
-> working          Claude starts answering
-> waiting          Claude asks you something
-> working          you answered, Claude continues
-> done             Claude finished
```

```bash
~/Applications/AgentDotWatch.app/Contents/MacOS/AgentDotWatch --dump | grep -E "STOP|SEND|INPUT"
```

`--dump` (with a Claude window open) lists the button labels the app exposes and marks the ones the watcher reacts to (`<- STOP`, `<- SEND`, `<- INPUT`). Run it once while Claude is answering and once while a permission prompt or question is open. The watcher looks for `stop response`, `stop generating` or `stop`; `send message` / `send` to find the message box; and `allow`, `always allow`, `deny`, `don't allow`, `decline`, `approve`, `reject`, `skip`, `submit` (prefix match, so `allow once` counts) for prompts. If an app update renames them, set your own labels:

```bash
echo "stop response,stop" > ~/.agentdot/stop_labels
launchctl kickstart -k gui/$(id -u)/com.agentdot.watch
```

### Settings

| File in `~/.agentdot/` / environment variable | Default |
|---|---|
| `host` / `AGENTDOT_HOST` | `agentdot.local` |
| `stop_labels` / `AGENTDOT_STOP_LABELS` | `stop response,stop generating,stop` |
| `send_labels` / `AGENTDOT_SEND_LABELS` | `send message,send` |
| `input_labels` / `AGENTDOT_INPUT_LABELS` | `allow,always allow,deny,don't allow,do not allow,decline,approve,reject,skip,submit` |
| `app_ids` / `AGENTDOT_APP_IDS` | `com.anthropic.claudefordesktop` |

### Uninstall

```bash
bash mac/install.sh --uninstall
```

### If Accessibility proves unreliable: Chrome DevTools Protocol

The Claude desktop app is an Electron (Chromium) app. If its accessibility tree ever stops exposing the Stop button, a fallback is to start it with a debugging port and read the page directly:

```bash
open -a Claude --args --remote-debugging-port=9222
curl -s http://127.0.0.1:9222/json      # lists pages and their webSocketDebuggerUrl
```

A small script can then connect to that WebSocket and evaluate `!!document.querySelector('button[aria-label*="Stop"]')` every 200 ms, sending `working` / `done` on changes exactly like the watcher. Caveats: the app has to be launched that way every time, an app update may block the flag, and anything on your Mac can talk to that port while it's open. That's why Accessibility is the default.

For claude.ai in a browser, the same idea works as a tiny browser extension or userscript that watches for the Stop button and calls `http://<light-ip>/s?c=…`.

## ntfy.sh relay plugin (optional)

Use this when the light isn't on the same network as your Mac, or you also want the **waiting** state from Cowork-style tasks. The Claude desktop app (chat and Cowork) can run work **in the cloud**, so it can't reach a light on your home network directly. Instead, a small plugin publishes the status to a private **ntfy.sh** topic. The firmware keeps a streaming connection to the same topic and reacts within about a second.

```
Claude app (cloud) ──POST "working s1a2b3"──► ntfy.sh/<topic> ──stream──► Agent Dot
```

### 1. Choose a private topic

```bash
python3 -c "import secrets; print('agentdot-' + secrets.token_hex(8))"
```

Anyone who knows the topic can change your light's colour, but nothing else. Commands that could harm the light, like `resetwifi`, are ignored when they come from the relay.

### 2. Put it in the firmware

Copy `firmware/AgentDot/secrets.example.h` to `secrets.h` (git-ignored) and set:

```cpp
#define CLOUD_TOPIC "agentdot-1a2b3c4d5e6f7a8b"
```

Upload. The Serial Monitor shows `[agentdot] relay: listening on ntfy.sh`. Note: the relay keeps a TLS connection open, which costs some battery.

```bash
curl -d working https://ntfy.sh/agentdot-1a2b3c4d5e6f7a8b    # light turns purple
curl -d idle    https://ntfy.sh/agentdot-1a2b3c4d5e6f7a8b    # back to teal
```

### 3. Install the plugin

1. Edit `integrations/claude-app/agent-dot/hooks/register.ts` and set `TOPIC` to the same topic.
2. Zip the `agent-dot` folder's **contents**, so that `.claude-plugin/` sits at the top of the zip, and name the file `agent-dot.plugin`.
3. In the Claude app, go to **Customize → Plugins → Add → Upload plugin**, and choose the file.
4. Allow the app to reach the internet: on claude.ai, go to **Settings → Capabilities** and turn on **Use the internet while making files**. Team and Enterprise plans need an admin to allow `ntfy.sh`.

### What the plugin does

| Event | Light |
|---|---|
| You send a message | working |
| Claude asks you a question / a permission prompt opens | waiting, then working again after you answer |
| Claude's reply ends | done (stays purple at least 1.5 s first, so quick replies still flash purple) |
| You stop Claude | idle |
| The turn fails | error |
| Long task | "working" re-sent every 8 minutes |

### Limits

ntfy.sh's free service limits **per internet address**: about **60 requests per 5 minutes** and **250 messages per day**, and the app's cloud machines share addresses with other users. Expect occasional delays, or no updates for the rest of the day once the quota is used. For reliable updates use a paid ntfy plan (add an `Authorization: Bearer` header in `deliver()`), self-host ntfy, or use the Mac watcher above.

Claude Code is not affected by any of this, because it talks to the light directly ([CLAUDE_CODE.md](CLAUDE_CODE.md)).
