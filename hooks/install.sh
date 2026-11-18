#!/usr/bin/env bash
# Installs the Agent Dot hooks for Claude Code (macOS / Linux).
#   bash hooks/install.sh                 -> finds the light via agentdot.local and remembers its IP
#   bash hooks/install.sh 192.168.1.42    -> uses this IP (fastest; reserve it in your router or set a fixed IP)
#   bash hooks/install.sh --uninstall     -> removes the hooks again
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
SETTINGS="$HOME/.claude/settings.json"
mkdir -p "$HOME/.agentdot" "$HOME/.claude"
[ -f "$SETTINGS" ] && cp "$SETTINGS" "$SETTINGS.bak"

if [ "$1" = "--uninstall" ]; then
  python3 - "$SETTINGS" <<'PY'
import json, sys
p = sys.argv[1]
try: s = json.load(open(p))
except Exception: sys.exit(0)
h = s.get('hooks', {})
for ev in list(h):
    h[ev] = [g for g in h[ev] if 'agentdot.sh' not in json.dumps(g)]
    if not h[ev]: del h[ev]
json.dump(s, open(p, 'w'), indent=2)
print('Agent Dot hooks removed from', p)
PY
  exit 0
fi

cp "$HERE/agentdot.sh" "$HOME/.agentdot/agentdot.sh"
chmod +x "$HOME/.agentdot/agentdot.sh"

# Remember the light's IP: requests to a plain IP skip the mDNS lookup (lower latency).
IP="$1"
if [ -z "$IP" ]; then
  IP=$(curl -s -m 4 http://agentdot.local/status | sed -n 's/.*"ip":"\([0-9.]*\)".*/\1/p')
  [ -n "$IP" ] && echo "Found the light at $IP"
fi
if [ -n "$IP" ]; then echo "$IP" > "$HOME/.agentdot/host"
else echo "Light not found right now - using agentdot.local. Re-run with its IP later for lower latency."; fi

python3 - "$SETTINGS" <<'PY'
import json, os, sys
p = sys.argv[1]
try:
    s = json.load(open(p))
except Exception:
    s = {}
hooks = s.setdefault('hooks', {})
cmd = os.path.expanduser('~/.agentdot/agentdot.sh')
want = {
    'SessionStart':     'idle',
    'UserPromptSubmit': 'working',
    'PreToolUse':       'working',
    'PostToolUse':      'working',   # back to purple right after you approve a permission prompt
    'Notification':     'waiting',   # permission prompt / question (idle reminders are filtered out)
    'Stop':             'done',
    'SessionEnd':       'idle',
}
for ev, state in want.items():
    lst = hooks.setdefault(ev, [])
    lst[:] = [g for g in lst if 'agentdot.sh' not in json.dumps(g)]
    entry = {'hooks': [{'type': 'command', 'command': f'{cmd} {state}', 'timeout': 5}]}
    if ev in ('PreToolUse', 'PostToolUse'):
        entry['matcher'] = '*'
    lst.append(entry)
json.dump(s, open(p, 'w'), indent=2)
print('Agent Dot hooks added to', p, '- restart Claude Code (or type /hooks to check).')
PY

"$HOME/.agentdot/agentdot.sh" working </dev/null && sleep 1.5
echo "Sent 'working' - the light should show the purple sweep. Sending 'idle' in 3 s..."
sleep 3; rm -f "${TMPDIR:-/tmp}/agentdot-none"; "$HOME/.agentdot/agentdot.sh" idle </dev/null
