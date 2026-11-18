# Claude Code integration

Claude Code runs on your computer, so it talks to the light **directly over your Wi-Fi**. No cloud service, and the delay is a few milliseconds.

## Install

```bash
cd ~/Downloads/"agent-dot 2"        # wherever the project is
bash hooks/install.sh 192.168.1.42  # your light's IP (recommended)
bash hooks/install.sh               # or: find it via agentdot.local and remember its IP
```

Use `bash hooks/install.sh` rather than `./hooks/install.sh`: macOS may refuse to run downloaded scripts directly. If even that says `Operation not permitted`, your terminal isn't allowed into the folder – see [INSTALL.md, step 0](INSTALL.md#0-before-you-start).

The installer:

- copies `hooks/agentdot.sh` to `~/.agentdot/`
- saves the light's IP in `~/.agentdot/host` (a plain IP skips the mDNS lookup on every request)
- backs up `~/.claude/settings.json` to `settings.json.bak`, then adds the hooks below. Your other settings are kept, and running it twice does no harm.
- sends a test **working** (purple), then **idle**

Then **restart Claude Code**. Type `/hooks` inside Claude Code to check that they're loaded. Remove them with `bash hooks/install.sh --uninstall`.

## What the hooks do

| Claude Code event | Light |
|---|---|
| `SessionStart` | idle |
| `UserPromptSubmit` (you send a prompt) | working |
| `PreToolUse` / `PostToolUse` (Claude runs a tool) | working |
| `Notification` (permission prompt / question) | waiting |
| `Stop` (Claude finished) | done |
| `SessionEnd` | idle |

The "Claude is waiting for your input" reminder that Claude Code sends about a minute after a reply is ignored: it just means it's your turn, so the light stays green, then teal.

## Why it never slows Claude down

`agentdot.sh` is written so that Claude Code never waits for the light:

- It returns in about 10–20 ms. The HTTP request runs in the **background**, detached from Claude Code's pipes, with a 0.8 s connect timeout and 1.5 s total.
- If the light is off, asleep or unreachable, the request just times out in the background. Nothing is printed and the hook always exits 0.
- `PreToolUse` fires on every tool call. The same state for the same session is sent at most once every 2 minutes, so a long run of tool calls costs one request, not hundreds.
- Each request carries a millisecond timestamp, so the light ignores one that arrives late (background requests can overtake each other).
- It tries the saved IP first, then `agentdot.local` as a fallback.

Each Claude Code session reports with its own id (from the hook's `session_id`), so several sessions at once are handled correctly.

## Manual install

Copy `hooks/agentdot.sh` to `~/.agentdot/`, `chmod +x` it, write your light's IP to `~/.agentdot/host`, and merge `hooks/hooks.json` into `~/.claude/settings.json`.

## Notes

- `AGENTDOT_HOST=192.168.1.42` in your environment overrides `~/.agentdot/host`.
- Give the light a fixed IP (router reservation, or the firmware's fixed-IP option) so the saved IP stays valid.
- macOS: allow **Local Network** access for your terminal (**System Settings → Privacy & Security → Local Network**).
- In zsh, put URLs containing `?` in quotes: `curl "http://192.168.1.42/s?c=working"`.
