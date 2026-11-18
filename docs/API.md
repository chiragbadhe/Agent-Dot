# API

The same commands work over **HTTP**, **Serial** (115200 baud, newline) and the optional **ntfy relay** (message body).

## States

| Command | Aliases | Light |
|---|---|---|
| `idle` | `ready` | dim teal breathe (dark after 10 quiet minutes) |
| `working` | `thinking`, `busy`, `tool` | purple sweep |
| `waiting` | `input`, `attention`, `permission` | amber pulse |
| `done` | `success`, `finished` | 3 green flashes, then green; idle after 1 min |
| `error` | `fail`, `failed` | red blink, then red breathe |
| `off` | – | LEDs off (until the next state) |

### Sessions

Add a session id to report several agents at once:

- **HTTP**: `/s?c=working&sid=s1a2b3`
- **Serial / relay**: `working s1a2b3`

The light shows the highest-priority session: **waiting > error > working > done > idle**.

- `idle <id>` removes that one session.
- A plain `idle` with no id clears every session.
- Commands without an id count as one session called `local`.
- Claude Code sessions use `c<last 6 chars of session id>`; the Mac watcher uses `app`.

### Ordering (`t`)

Senders that fire requests in the background can add `t=<unix time in ms>`. The light ignores a request for a session that is older than the last one it accepted for that session, so a late "working" can never overwrite a newer "done". Without `t`, the last request to arrive wins.

## HTTP endpoints

| Endpoint | |
|---|---|
| `GET /s?c=<state>[&sid=<id>][&t=<ms>]` | **fast path** – set a state, replies `ok` (no JSON); `s=` works as well as `c=` |
| `GET/POST /state?s=<state>[&sid=<id>][&t=<ms>]` | same, replies with the status JSON (also accepts a body `working` or `{"state":"working"}`) |
| `GET /` | control page with buttons, brightness and colour |
| `GET /color?hex=ff00ff&anim=breathe` | custom colour (`solid`, `breathe`, `blink`, `chase`) |
| `GET /brightness?v=40` | brightness (capped at `MAX_BRIGHTNESS`, saved) |
| `GET /status` | JSON: state, brightness, wifi, ip, rssi, host, fixed_ip, cpu_mhz, uptime |
| `GET /staticip?ip=192.168.1.42&gw=192.168.1.1` | save a fixed IP (`/24` network) and restart; `?ip=off` goes back to DHCP |
| `GET /reset-wifi` | forget Wi-Fi and reopen the setup network |

## Serial-only extras

| Command | Example |
|---|---|
| `color <RRGGBB> [solid\|breathe\|blink\|chase]` | `color ff00ff breathe` |
| `brightness <0-255>` | `brightness 40` |
| `staticip <ip> <gateway>` / `staticip off` | `staticip 192.168.1.42 192.168.1.1` |
| `status` | prints JSON |
| `resetwifi` (ignored from the relay) | forgets Wi-Fi |

## Examples

```bash
curl "http://192.168.1.42/s?c=working&sid=build1"
curl "http://192.168.1.42/s?c=done&sid=build1"
curl "http://agentdot.local/status"
```

Use it from anything: CI jobs, other AI agents, long shell commands:

```bash
make; curl -s -m 1 "http://192.168.1.42/s?c=done" >/dev/null &
```

For anything that must never wait on the light, copy the pattern in `hooks/agentdot.sh`: short `--connect-timeout`/`-m`, run in the background with stdin/stdout/stderr redirected.
