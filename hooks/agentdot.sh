#!/bin/sh
# Agent Dot - Claude Code hook.        agentdot.sh working|waiting|done|error|idle
#
# Built to never slow Claude down:
#   - returns in a few milliseconds; the HTTP request runs in the background (detached from
#     Claude Code's pipes) with short timeouts, so an offline light is silently ignored
#   - repeated identical states (PreToolUse fires on every tool call) are skipped for 2 minutes
#   - every request carries a millisecond timestamp, so the light ignores one that arrives late
#   - fixed IP first (~/.agentdot/host or $AGENTDOT_HOST), agentdot.local (mDNS) as the fallback
STATE="${1:-idle}"
CONF="$HOME/.agentdot"
FALLBACK="agentdot.local"
HOST="${AGENTDOT_HOST:-}"
[ -z "$HOST" ] && [ -r "$CONF/host" ] && HOST=$(cat "$CONF/host" 2>/dev/null)
[ -z "$HOST" ] && HOST="$FALLBACK"

SID=""
if [ ! -t 0 ]; then                                   # Claude Code passes the event as JSON on stdin
  IN=$(cat 2>/dev/null)
  SID=$(printf '%s' "$IN" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1 | tr -cd 'a-zA-Z0-9' | tail -c 6)
  if [ "$STATE" = "waiting" ]; then
    # Only real "needs you" notifications turn the light amber. "Claude is waiting for your input"
    # (idle_prompt, ~60 s after a reply) just means it's your turn - keep showing done/idle.
    case "$IN" in
      *'"idle_prompt"'*|*'"auth_success"'*|*'waiting for your input'*) exit 0 ;;
    esac
  fi
fi

# skip duplicates: same state for this session sent less than 2 minutes ago
CACHE="${TMPDIR:-/tmp}/agentdot-${SID:-none}"
if [ -f "$CACHE" ] && [ "$(cat "$CACHE" 2>/dev/null)" = "$STATE" ] && [ -n "$(find "$CACHE" -mmin -2 2>/dev/null)" ]; then
  exit 0
fi
printf '%s' "$STATE" > "$CACHE" 2>/dev/null

T=$(perl -MTime::HiRes=time -e 'printf "%.0f", time*1000' 2>/dev/null)
[ -z "$T" ] && T="$(date +%s)000"
Q="/s?c=${STATE}&sid=c${SID}&t=${T}"

(
  curl -s -o /dev/null --connect-timeout 0.8 -m 1.5 "http://${HOST}${Q}" ||
  { [ "$HOST" != "$FALLBACK" ] && curl -s -o /dev/null --connect-timeout 1.5 -m 2.5 "http://${FALLBACK}${Q}"; }
) </dev/null >/dev/null 2>&1 &

exit 0
