import type { EngineInterface, Register } from 'claude-code'

// Agent Dot: shows what Claude is doing on a small RGB light, through a private ntfy.sh topic.
// The firmware listens on the same topic (CLOUD_TOPIC in AgentDot.ino). Keep both the same.
//
// Every message is "<state> <session>", so the light can follow several chats at once and show the most
// important one (waiting > error > working > done > idle). Cases handled:
//   - you send a message                       -> working (purple), even during the green "done" minute
//   - Claude asks you something / needs a yes  -> waiting (amber), then working again once you answer
//   - Claude finishes                          -> done (green); the light fades to idle by itself after a minute
//   - you stop Claude                          -> idle;  a failed turn -> error (red)
//   - long tasks                               -> "working" is re-sent every few minutes so the light never times out
//   - the relay is busy (HTTP 429) or slow     -> retried; a newer state always wins over an older retry
//   - the session ends                         -> idle for this session only
const TOPIC = 'agentdot-CHANGE-ME' // your own random topic; must match CLOUD_TOPIC in the firmware
const URL = `https://ntfy.sh/${TOPIC}`
const HEARTBEAT_MS = 8 * 60_000 // re-send an unchanged state at most this often (ntfy.sh allows ~250 messages a day)
const LOG = '/tmp/agentdot-mod.log'

type LightState = 'idle' | 'working' | 'waiting' | 'done' | 'error'

let last: LightState | undefined
let lastAt = 0
let warned = false
let sid = ''
const lines: string[] = []

function log($: EngineInterface, line: string): void {
  lines.push(`${new Date().toISOString().slice(11, 19)} ${line}`)
  if (lines.length > 80) lines.shift()
  $.fs.write(LOG, lines.join('\n') + '\n').catch(() => undefined)
}

function send($: EngineInterface, state: LightState, force = false): void {
  const now = Date.now()
  if (!force && state === last && now - lastAt < HEARTBEAT_MS) return
  if (state === last && now - lastAt < 5000) return // same state twice in a row (e.g. question + permission check)
  last = state
  lastAt = now
  try {
    $.ui.status(`Agent Dot: ${state}`)
  } catch {
    // no status line on this surface
  }
  pending = state // newest wins over anything still waiting (not over the one being sent)
  if (!pumping) pump($).catch((err: unknown) => log($, `pump failed ${String(err).slice(0, 200)}`))
}

// Sends states one at a time, IN ORDER, so a quick reply still shows purple before green:
// "working" is delivered (retrying if the relay is busy) before the "done" that follows it,
// and purple stays up at least MIN_WORKING_MS.
const MIN_WORKING_MS = 1500
let pending: LightState | undefined
let pumping = false
let workingAt = 0

async function pump($: EngineInterface): Promise<void> {
  pumping = true
  try {
    while (pending !== undefined) {
      const state = pending
      pending = undefined
      if (state !== 'working' && workingAt > 0) {
        const wait = workingAt + MIN_WORKING_MS - Date.now()
        if (wait > 0) await $.clock.sleep(wait)
      }
      const ok = await deliver($, state)
      if (ok && state === 'working') workingAt = Date.now()
      else if (ok) workingAt = 0
    }
  } finally {
    pumping = false
  }
}

// curl goes through this workspace's network proxy (the engine's own fetch has no route out here).
async function deliver($: EngineInterface, state: LightState): Promise<boolean> {
  if (sid === '') {
    try {
      const id = await $.session.id()
      sid = 's' + id.replace(/[^a-zA-Z0-9]/g, '').slice(-6)
    } catch {
      sid = 's' + Math.random().toString(36).slice(2, 8)
    }
  }
  for (let attempt = 1; attempt <= 6; attempt++) {
    const r = await $.process.run(
      ['curl', '-sS', '-m', '8', '-o', '/dev/null', '-w', '%{http_code}', '-d', `${state} ${sid}`, URL],
      { timeoutMs: 15_000 },
    )
    const code = r.stdout.trim()
    log($, `${state} ${sid}: try ${attempt} -> HTTP ${code || '-'}${r.exitCode ? ` exit ${r.exitCode}` : ''}`)
    if (r.exitCode === 0 && code === '200') {
      warned = false
      return true
    }
    if (pending !== undefined && attempt >= 3) return false // a newer state is waiting: move on to it
    await $.clock.sleep(Math.min(attempt * 2000, 6000))
  }
  if (!warned) {
    warned = true
    try {
      $.ui.status('Agent Dot: relay unreachable')
    } catch {
      // no status line on this surface
    }
  }
  return false
}

export const register: Register = on => {
  on('prompt.submit', ($, e, next) => {
    send($, 'working', true)
    return next(e)
  })

  on('tool.check', async ($, e, next) => {
    const verdict = await next(e)
    if (verdict.decision === 'ask') send($, 'waiting', true) // a permission prompt waits for the person
    return verdict
  })

  on('tool.call', async ($, e, next) => {
    const asks = e.tool === 'AskUserQuestion'
    if (asks) send($, 'waiting', true)
    else if (last !== 'waiting') send($, 'working') // forced only after a while: keeps long tasks alive
    const result = await next(e)
    if (last === 'waiting') send($, 'working', true) // the person answered or approved
    return result
  })

  on('turn.complete', ($, e, next) => {
    if (e.agentId === undefined) {
      log($, `turn.complete ${e.reason}`)
      send($, e.reason === 'answer' ? 'done' : e.reason === 'aborted' ? 'idle' : 'error', true)
    }
    return next(e)
  })

  on('session.end', ($, e, next) => {
    send($, 'idle', true)
    return next(e)
  })
}
