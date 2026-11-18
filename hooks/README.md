# Claude Code hooks

| File | What it is |
|---|---|
| `agentdot.sh` | the hook: sends a state to the light in the background and returns in ~15 ms |
| `install.sh` | installs it to `~/.agentdot/`, saves the light's IP, merges the hooks into `~/.claude/settings.json` (`--uninstall` removes them) |
| `hooks.json` | the hook block, for merging by hand |

```bash
bash hooks/install.sh 192.168.1.42    # from the project folder; your light's IP
```

Step by step: [docs/INSTALL.md](../docs/INSTALL.md#5-claude-code-hooks) · details: [docs/CLAUDE_CODE.md](../docs/CLAUDE_CODE.md).
