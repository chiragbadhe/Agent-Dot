# AgentDotWatch (Claude desktop app → Agent Dot)

| File | What it is |
|---|---|
| `AgentDotWatch.swift` | watches the Claude app via Accessibility; sends `working` while the Stop button is visible, `waiting` while an Allow / Deny / Submit / Skip prompt is open, `done` 2.5 s after both are gone |
| `install.sh` | builds it into `~/Applications/AgentDotWatch.app`, installs and starts the launchd agent (`--uninstall` removes it) |
| `com.agentdot.watch.plist` | launchd template used by `install.sh` (runs at login, restarts if it exits) |

```bash
xcode-select --install              # once, if you don't have Apple's command line tools
bash mac/install.sh 192.168.1.42    # from the project folder; your light's IP
```

Then allow **Accessibility** (and **Local Network**) for AgentDotWatch. After a rebuild, remove it from the Accessibility list and add it again. Step by step: [docs/INSTALL.md](../docs/INSTALL.md#6-claude-desktop-app-agentdotwatch) · details: [docs/CLAUDE_APP.md](../docs/CLAUDE_APP.md).
