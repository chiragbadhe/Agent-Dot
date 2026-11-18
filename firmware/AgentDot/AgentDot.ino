/*
  Agent Dot - AI agent status light            https://github.com/<you>/agent-dot   (MIT License)

  Board : Seeed XIAO ESP32C3 ("XIAO_ESP32C3"), ESP32-C3 SuperMini ("ESP32C3 Dev Module")
          or ESP32-S3 SuperMini ("ESP32S3 Dev Module").   Tools > USB CDC On Boot: Enabled
  LEDs  : 3 x WS2812B / SK6812 (GRB) on LED_PIN (default GPIO10) through a 330 ohm resistor
  Power : 1S LiPo -> TP4056 (OUT+/OUT-) -> switch -> board 5V pin + LED strip VDD

  Libraries (Arduino Library Manager):
    - Adafruit NeoPixel        (by Adafruit)
    - WiFiManager              (by tzapu, v2.0.17 or newer)

  Control (same commands everywhere - see docs/API.md)
    1. Wi-Fi  : http://agentdot.local/s?c=working&sid=<session>   (short form; /state?s= also works)
    2. USB    : type "working" in the Serial Monitor (115200 baud) - works without Wi-Fi
    3. Relay  : POST "working <session>" to https://ntfy.sh/<CLOUD_TOPIC>  (for cloud agents)

  States (several sessions at once: waiting > error > working > done > idle)
    idle     - very dim teal breathe
    working  - purple sweep
    waiting  - amber pulse (the agent needs you)
    done     - green flashes, then green; back to idle after DONE_HOLD_MS
    error    - red blink, then red breathe
    off      - LEDs off
  Extra commands
    color <hex> [solid|breathe|blink|chase]   e.g.  color ff00ff breathe
    brightness <0-255>                         (capped at MAX_BRIGHTNESS, saved)
    status                                     (prints JSON)
    staticip <ip> <gateway> | staticip off     (fixed IP, saved; restarts)
    resetwifi                                  (forget Wi-Fi, reopen the setup portal)

  First start: the light blinks white and opens a Wi-Fi network called "AgentDot-Setup".
  Join it, pick your Wi-Fi, enter the password (and optionally a fixed IP), save.
  No passwords live in this file: optional build-time Wi-Fi goes in secrets.h (git-ignored).

  Power: CPU at 80 MHz, Wi-Fi modem sleep, the idle glow goes dark after IDLE_DARK_AFTER_MS,
  then the radio drops to deeper modem sleep (wakes on the next request, ~0.1-0.3 s extra).
  Optional deep sleep after DEEP_SLEEP_AFTER_MIN (wake with a button or the power switch).
*/

#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <Preferences.h>
#include <WiFiManager.h>
#include <Adafruit_NeoPixel.h>
#include <WiFiClientSecure.h>
#include <esp_sleep.h>

// Optional secrets (git-ignored): copy secrets.example.h to secrets.h. Everything works without it.
#if __has_include("secrets.h")
#include "secrets.h"
#endif

// ---------------------------------------------------------------- settings
#define LED_PIN            10      // LED strip DIN (through 330 ohm)
#define NUM_LEDS           3
#define LED_TYPE           (NEO_GRB + NEO_KHZ800)   // SK6812 RGBW strips: use NEO_GRBW + NEO_KHZ800
#define MAX_BRIGHTNESS     90                       // hard cap (0-255): keeps current and heat low on a 400 mAh cell
#define DEFAULT_BRIGHTNESS 60

// ---- Cloud relay: lets the Claude app (which runs in the cloud) reach this light through ntfy.sh.
//      Keep the topic secret-ish (anyone who knows it can change your light's colour). "" turns it off.
//      Set it in secrets.h:  #define CLOUD_TOPIC "agentdot-<random>"   (see docs/CLAUDE_APP.md)
#ifndef CLOUD_TOPIC
#define CLOUD_TOPIC ""                 // "" = relay off (recommended on a Mac: use the local watcher instead)
#endif

// ---- Wi-Fi (optional): put WIFI_SSID / WIFI_PASS in secrets.h to skip the AgentDot-Setup page.
#ifndef WIFI_SSID
#define WIFI_SSID  ""
#endif
#ifndef WIFI_PASS
#define WIFI_PASS  ""
#endif

// ---- Power
#define CPU_MHZ              80     // 80 MHz is plenty for this job and saves ~10 mA vs 160 MHz
#define IDLE_DARK_AFTER_MS   (10UL * 60 * 1000)  // idle glow fades out after 10 min with no news (0 = never)
#define DEEP_SLEEP_AFTER_MIN 0      // deep sleep after N min with no news (0 = never). Wi-Fi is OFF in deep sleep,
                                    // so requests can't wake it: only WAKE_PIN or the power switch can.
#define WAKE_PIN             -1     // button to GND that wakes from deep sleep. C3: GPIO 0-5 only
                                    // (XIAO D0..D3 = GPIO2..5). -1 = none (use the power switch).

const char*    HOSTNAME     = "agentdot";           // -> http://agentdot.local
const char*    AP_NAME      = "AgentDot-Setup";     // Wi-Fi setup network
const uint32_t DONE_HOLD_MS = 60UL * 1000;          // "done" turns back to idle after 1 minute
const uint32_t STALE_MS     = 30UL * 60 * 1000;     // a session with no news for 30 min (crashed, closed) is dropped
const uint16_t FRAME_MS     = 20;                   // 50 fps while something is happening
const uint16_t SLOW_FRAME_MS = 50;                  // 20 fps for the slow idle breathe (saves CPU)

// ---------------------------------------------------------------- globals
Adafruit_NeoPixel strip(NUM_LEDS, LED_PIN, LED_TYPE);
WebServer  server(80);
WiFiManager wm;
Preferences prefs;

enum State { ST_OFF, ST_IDLE, ST_WORKING, ST_WAITING, ST_DONE, ST_ERROR, ST_CUSTOM, ST_SETUP, ST_BOOT };
enum Anim  { AN_SOLID, AN_BREATHE, AN_BLINK, AN_CHASE };

State    state        = ST_BOOT;
uint32_t stateSince   = 0;     // when the current state started
uint32_t lastUpdate   = 0;     // last command received
uint8_t  brightness   = DEFAULT_BRIGHTNESS;
uint32_t customColor  = 0xFFFFFF;
Anim     customAnim   = AN_SOLID;
bool     netReady     = false; // web server + mDNS running
uint32_t lastFrame    = 0;
String   serialLine;

// ---------------------------------------------------------------- helpers
static const char* stateName(State s) {
  switch (s) {
    case ST_OFF: return "off";        case ST_IDLE: return "idle";
    case ST_WORKING: return "working"; case ST_WAITING: return "waiting";
    case ST_DONE: return "done";      case ST_ERROR: return "error";
    case ST_CUSTOM: return "custom";  case ST_SETUP: return "setup";
    default: return "boot";
  }
}

static uint32_t rgb(uint8_t r, uint8_t g, uint8_t b) { return strip.Color(r, g, b); }

// scale a 0xRRGGBB colour by k (0..1)
static uint32_t scaled(uint32_t c, float k) {
  if (k < 0) k = 0;
  if (k > 1) k = 1;
  uint8_t r = (c >> 16) & 0xFF, g = (c >> 8) & 0xFF, b = c & 0xFF;
  return strip.Color((uint8_t)(r * k), (uint8_t)(g * k), (uint8_t)(b * k));
}

// smooth 0..1..0 wave with the given period
static float breathe(uint32_t t, uint32_t period) {
  return 0.5f - 0.5f * cosf(2.0f * PI * (float)(t % period) / (float)period);
}

static void fillAll(uint32_t c) {
  for (int i = 0; i < NUM_LEDS; i++) strip.setPixelColor(i, c);
}

// bouncing "scanner" across the LEDs
static void scanner(uint32_t c, uint32_t t, uint32_t period, float floorLevel) {
  float ph = (float)(t % period) / (float)period;           // 0..1
  float tri = ph < 0.5f ? ph * 2.0f : 2.0f - ph * 2.0f;     // 0..1..0
  float pos = tri * (NUM_LEDS - 1);
  for (int i = 0; i < NUM_LEDS; i++) {
    float d = fabsf(i - pos);
    float k = d < 1.0f ? (1.0f - d) : 0.0f;
    k = floorLevel + (1.0f - floorLevel) * k * k;
    strip.setPixelColor(i, scaled(c, k));
  }
}

static void setState(State s) {
  if (s != state) stateSince = millis();
  state = s;
  lastUpdate = millis();
  lastFrame = 0;                       // draw the new state on the very next loop pass (no frame wait)
  Serial.printf("[agentdot] state -> %s\n", stateName(s));
}

static bool parseHex(String h, uint32_t &out) {
  h.trim(); h.replace("#", "");
  if (h.length() != 6) return false;
  for (unsigned i = 0; i < h.length(); i++) if (!isxdigit(h[i])) return false;
  out = strtoul(h.c_str(), nullptr, 16);
  return true;
}

static Anim parseAnim(String a) {
  a.toLowerCase();
  if (a == "breathe" || a == "pulse") return AN_BREATHE;
  if (a == "blink")                   return AN_BLINK;
  if (a == "chase" || a == "scan")    return AN_CHASE;
  return AN_SOLID;
}

static void setBrightnessValue(int v) {
  if (v < 0) v = 0;
  if (v > MAX_BRIGHTNESS) v = MAX_BRIGHTNESS;
  brightness = (uint8_t)v;
  strip.setBrightness(brightness);
  prefs.putUChar("bright", brightness);
}

static String statusJson() {
  String j = "{";
  j += "\"state\":\"" + String(stateName(state)) + "\",";
  j += "\"brightness\":" + String(brightness) + ",";
  j += "\"max_brightness\":" + String(MAX_BRIGHTNESS) + ",";
  j += "\"wifi\":" + String(WiFi.status() == WL_CONNECTED ? "true" : "false") + ",";
  j += "\"ip\":\"" + (WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString() : String("")) + "\",";
  j += "\"rssi\":" + String(WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : 0) + ",";
  j += "\"host\":\"" + String(HOSTNAME) + ".local\",";
  j += "\"fixed_ip\":" + String(prefs.isKey("sip") ? "true" : "false") + ",";
  j += "\"cpu_mhz\":" + String(getCpuFrequencyMhz()) + ",";
  j += "\"uptime_s\":" + String(millis() / 1000);
  j += "}";
  return j;
}

// ---------------------------------------------------------------- several agents at once
// Every Claude chat / Claude Code session reports its own state, e.g. "working s1a2b".
// The light shows the most important one: waiting > error > working > done > idle.
//   - a new message during the green "done" -> that session goes "working" -> purple at once
//   - one chat finishes while another still works -> stays purple
//   - "done" fades to idle after DONE_HOLD_MS; working/waiting/error with no news for STALE_MS -> idle
struct Agent { String id; State st; uint32_t at; uint64_t t; };   // t = sender's clock (ms), optional
static const int MAX_AGENTS = 8;
Agent agents[MAX_AGENTS];
bool agentMode = true;          // false while a manual colour / "off" is shown

static int prio(State s) {
  switch (s) { case ST_WAITING: return 4; case ST_ERROR: return 3; case ST_WORKING: return 2; case ST_DONE: return 1; default: return 0; }
}

static bool stateFromName(String c, State &out) {
  c.toLowerCase();
  if (c == "idle" || c == "ready")                                           { out = ST_IDLE; return true; }
  if (c == "working" || c == "thinking" || c == "busy" || c == "tool")       { out = ST_WORKING; return true; }
  if (c == "waiting" || c == "input" || c == "attention" || c == "permission") { out = ST_WAITING; return true; }
  if (c == "done" || c == "success" || c == "finished")                      { out = ST_DONE; return true; }
  if (c == "error" || c == "fail" || c == "failed")                          { out = ST_ERROR; return true; }
  return false;
}

static State agentAggregate() {
  uint32_t now = millis();
  State best = ST_IDLE;
  for (int i = 0; i < MAX_AGENTS; i++) {
    Agent &a = agents[i];
    if (a.id.length() == 0) continue;
    uint32_t age = now - a.at;
    if ((a.st == ST_DONE && age > DONE_HOLD_MS) || age > STALE_MS) { a.id = ""; continue; }   // expired
    if (prio(a.st) > prio(best)) best = a.st;
  }
  return best;
}

static void agentRefresh() {
  State s = agentAggregate();
  if (s != state) setState(s);
}

// The last few sessions that went idle, with their timestamp, so a late "working" for a session that
// already ended can't bring it back (hooks send in the background, so requests may arrive out of order).
static const int MAX_GONE = 4;
struct Gone { String id; uint64_t t; } gone[MAX_GONE];
static int goneNext = 0;

// ageMs: how old the report already is (a message replayed by the relay after a reconnect)
// t    : sender's timestamp in ms (0 = unknown). Older than what we have for that session -> ignored.
static void agentSet(String id, State st, uint32_t ageMs, uint64_t t) {
  if (st == ST_IDLE && id.length() == 0) {                       // plain "idle" (web page / serial): clear everything
    for (int i = 0; i < MAX_AGENTS; i++) agents[i].id = "";
  } else {
    if (id.length() == 0) id = "local";
    if (t) for (int i = 0; i < MAX_GONE; i++) if (gone[i].id == id && t <= gone[i].t) return;   // stale
    int slot = -1;
    for (int i = 0; i < MAX_AGENTS && slot < 0; i++) if (agents[i].id == id) slot = i;
    if (slot >= 0 && t && agents[slot].t && t < agents[slot].t) return;                       // stale, newer already shown
    if (slot < 0) for (int i = 0; i < MAX_AGENTS && slot < 0; i++) if (agents[i].id.length() == 0) slot = i;
    if (slot < 0) { slot = 0; for (int i = 1; i < MAX_AGENTS; i++) if ((int32_t)(agents[i].at - agents[slot].at) < 0) slot = i; }
    if (st == ST_IDLE) {                                         // that session ended / was stopped
      agents[slot].id = "";
      if (t) { gone[goneNext].id = id; gone[goneNext].t = t; goneNext = (goneNext + 1) % MAX_GONE; }
    } else { agents[slot].id = id; agents[slot].st = st; agents[slot].at = millis() - ageMs; agents[slot].t = t; }
  }
  agentMode = true;
  lastUpdate = millis();
  State s = agentAggregate();
  if (s != state) setState(s);
  else if (s == ST_DONE && st == ST_DONE) stateSince = millis() - ageMs;   // another chat finished: full green again
}

// ---------------------------------------------------------------- fixed IP (optional, saved in flash)
// A fixed IP skips DHCP (faster reconnects) and lets clients skip mDNS lookups (lower latency).
uint32_t restartAt = 0;          // deferred restart, so an HTTP reply can go out first

static bool saveStaticIp(String ip, String gw) {
  ip.trim(); gw.trim();
  if (ip.length() == 0 || ip == "off" || ip == "dhcp") { prefs.remove("sip"); prefs.remove("sgw"); return true; }
  IPAddress a, g;
  if (!a.fromString(ip) || !g.fromString(gw)) return false;
  prefs.putString("sip", ip); prefs.putString("sgw", gw);
  return true;
}

static bool loadStaticIp(IPAddress &ip, IPAddress &gw, IPAddress &mask) {
  if (!prefs.isKey("sip") || !prefs.isKey("sgw")) return false;
  if (!ip.fromString(prefs.getString("sip", "")) || !gw.fromString(prefs.getString("sgw", ""))) return false;
  mask = IPAddress(255, 255, 255, 0);                            // typical home network (/24)
  return true;
}

// one parser for Wi-Fi and Serial. Returns false if the command is unknown.
static bool runCommand(String cmd, String a1, String a2) {
  cmd.trim(); cmd.toLowerCase(); a1.trim(); a2.trim();
  State st;
  if (stateFromName(cmd, st)) { agentSet(a1, st, 0, 0); return true; }         // a1 = optional session id
  if (cmd == "off")           { agentMode = false; setState(ST_OFF); return true; }
  if (cmd == "color" || cmd == "colour") {
    uint32_t c;
    if (!parseHex(a1, c)) return false;
    customColor = c; customAnim = parseAnim(a2);
    agentMode = false;
    setState(ST_CUSTOM);
    stateSince = millis();
    return true;
  }
  if (cmd == "brightness") { setBrightnessValue(a1.toInt()); lastUpdate = millis(); return true; }
  if (cmd == "status")     { Serial.println(statusJson()); return true; }
  if (cmd == "staticip") {
    if (!saveStaticIp(a1, a2)) return false;
    Serial.printf("[agentdot] fixed IP %s - restarting\n", (a1.length() && a1 != "off" && a1 != "dhcp") ? a1.c_str() : "off (DHCP)");
    restartAt = millis() + 500;
    return true;
  }
  if (cmd == "resetwifi")  { Serial.println("[agentdot] forgetting Wi-Fi and restarting"); wm.resetSettings(); delay(300); ESP.restart(); return true; }
  return false;
}

// ---------------------------------------------------------------- animation
static void renderFrame() {
  uint32_t now = millis();
  uint32_t t = now - stateSince;

  // per-session timeouts (done -> idle after DONE_HOLD_MS, stale sessions dropped)
  if (agentMode && state != ST_BOOT && state != ST_SETUP) agentRefresh();
  t = millis() - stateSince;

  switch (state) {
    case ST_OFF:
      fillAll(0);
      break;

    case ST_BOOT: {                                   // quick rainbow sweep at power-on
      for (int i = 0; i < NUM_LEDS; i++)
        strip.setPixelColor(i, strip.gamma32(strip.ColorHSV((uint16_t)(t * 60 + i * 21845))));
      if (t > 1200) setState(ST_IDLE);
      break;
    }

    case ST_SETUP:                                    // waiting for Wi-Fi setup: slow white blink
      fillAll(((t / 700) % 2) ? rgb(40, 40, 40) : rgb(180, 180, 180));
      break;

    case ST_IDLE: {                                   // very dim teal breathe; fades to dark after IDLE_DARK_AFTER_MS
      float k = 0.04f + 0.14f * breathe(t, 4000);
      uint32_t quiet = now - lastUpdate;
      if (IDLE_DARK_AFTER_MS > 0 && quiet > IDLE_DARK_AFTER_MS) {
        uint32_t f = quiet - IDLE_DARK_AFTER_MS;
        k = (f >= 3000) ? 0.0f : k * (1.0f - f / 3000.0f);
      }
      fillAll(scaled(rgb(0, 160, 200), k));
      break;
    }

    case ST_WORKING:                                  // purple scanner
      scanner(rgb(140, 50, 255), t, 1100, 0.08f);
      break;

    case ST_WAITING:                                  // amber pulse - needs you
      fillAll(scaled(rgb(255, 120, 0), 0.15f + 0.85f * breathe(t, 1200)));
      break;

    case ST_DONE:                                     // 3 quick green flashes, then steady green, fading near the end
      if (t < 900) fillAll(((t / 150) % 2) ? 0 : rgb(0, 255, 60));
      else {
        float k = 1.0f;
        if (t > DONE_HOLD_MS - 3000) k = (float)(DONE_HOLD_MS - t) / 3000.0f;
        fillAll(scaled(rgb(0, 255, 60), 0.6f * k));
      }
      break;

    case ST_ERROR:                                    // fast red blink for 2 s, then red breathe
      if (t < 2000) fillAll(((t / 200) % 2) ? 0 : rgb(255, 0, 0));
      else          fillAll(scaled(rgb(255, 0, 0), 0.2f + 0.8f * breathe(t, 2000)));
      break;

    case ST_CUSTOM:
      switch (customAnim) {
        case AN_SOLID:   fillAll(scaled(customColor, 1.0f)); break;
        case AN_BREATHE: fillAll(scaled(customColor, 0.1f + 0.9f * breathe(t, 2000))); break;
        case AN_BLINK:   fillAll(((t / 400) % 2) ? 0 : scaled(customColor, 1.0f)); break;
        case AN_CHASE:   scanner(customColor, t, 1100, 0.08f); break;
      }
      break;
  }
  // only push data to the LEDs when a pixel actually changed (dark idle = no work at all)
  static uint32_t lastSum = 0xFFFFFFFF;
  uint32_t sum = 2166136261u;
  for (int i = 0; i < NUM_LEDS; i++) sum = (sum ^ strip.getPixelColor(i)) * 16777619u;
  if (sum != lastSum) { strip.show(); lastSum = sum; }
}

// how often to draw: fast while something moves, slower for the idle breathe, rarely when dark
static uint16_t frameInterval() {
  if (state == ST_OFF) return 250;
  if (state == ST_IDLE) return (IDLE_DARK_AFTER_MS > 0 && millis() - lastUpdate > IDLE_DARK_AFTER_MS + 3000) ? 250 : SLOW_FRAME_MS;
  return FRAME_MS;
}

// ---------------------------------------------------------------- cloud relay (ntfy.sh)
WiFiClientSecure cloud;
uint32_t cloudLastData = 0, cloudRetryAt = 0;
bool     cloudInBody = false;
long     cloudOpenTime = 0;                   // server time (s) when the stream opened

static long jsonNum(const String &l, const char *key) {
  int k = l.indexOf(key);
  if (k < 0) return 0;
  return atol(l.c_str() + k + strlen(key));
}
String   cloudLine;

static void cloudLoop() {
  if (strlen(CLOUD_TOPIC) == 0 || WiFi.status() != WL_CONNECTED) return;
  uint32_t now = millis();
  if (!cloud.connected()) {
    if ((int32_t)(now - cloudRetryAt) < 0) return;
    cloudRetryAt = now + 5000;
    cloud.setInsecure();                       // status colours only - no secrets travel here
    if (!cloud.connect("ntfy.sh", 443, 5000)) { Serial.println("[agentdot] relay: connect failed, retrying"); return; }
    cloud.print(String("GET /") + CLOUD_TOPIC + "/json?since=10m HTTP/1.0\r\nHost: ntfy.sh\r\nUser-Agent: AgentDot\r\n\r\n");
    cloudOpenTime = 0;
    cloudInBody = false; cloudLine = ""; cloudLastData = now;
    Serial.println("[agentdot] relay: listening on ntfy.sh");
    return;
  }
  while (cloud.available()) {
    char c = cloud.read();
    cloudLastData = now;
    if (c != '\n') { if (cloudLine.length() < 600) cloudLine += c; continue; }
    String l = cloudLine; l.trim(); cloudLine = "";
    if (!cloudInBody) {                         // HTTP headers
      if (l.startsWith("HTTP/") && l.indexOf(" 200") < 0) { Serial.println("[agentdot] relay: " + l); cloud.stop(); cloudRetryAt = now + 30000; return; }
      if (l.length() == 0) cloudInBody = true;
      continue;
    }
    if (l.length() == 0) continue;
    // ntfy JSON lines: {"event":"open","time":...} then {"event":"message","time":...,"message":"working s1a2"}
    long tm = jsonNum(l, "\"time\":");
    if (l.indexOf("\"event\":\"open\"") >= 0) { cloudOpenTime = tm; continue; }
    if (l.indexOf("\"event\":\"message\"") < 0) continue;      // keepalive etc.
    uint32_t ageMs = (cloudOpenTime > 0 && tm > 0 && tm < cloudOpenTime) ? (uint32_t)(cloudOpenTime - tm) * 1000UL : 0;
    int m = l.indexOf("\"message\":\"");
    if (m < 0) continue;
    int e2 = l.indexOf('"', m + 11);
    l = l.substring(m + 11, e2);
    String p[3]; int n = 0, st = 0;
    for (int i = 0; i <= (int)l.length() && n < 3; i++)
      if (i == (int)l.length() || l[i] == ' ') { if (i > st) p[n++] = l.substring(st, i); st = i + 1; }
    if (p[0] == "resetwifi") continue;           // never accept this one from the internet
    State as;
    if (stateFromName(p[0], as)) { agentSet(p[1], as, ageMs, 0); Serial.println("[agentdot] relay: " + l + (ageMs ? " (replayed)" : "")); }
    else if (runCommand(p[0], p[1], p[2])) Serial.println("[agentdot] relay: " + l);
  }
  if (now - cloudLastData > 120000) { Serial.println("[agentdot] relay: idle too long, reconnecting"); cloud.stop(); }
}

// ---------------------------------------------------------------- web server
static const char INDEX_HTML[] PROGMEM = R"HTML(
<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent Dot</title><style>
body{font-family:-apple-system,system-ui,sans-serif;background:#111;color:#eee;max-width:420px;margin:24px auto;padding:0 16px}
h1{font-size:20px}button{width:48%;margin:1%;padding:14px;border:0;border-radius:10px;font-size:15px;color:#fff;cursor:pointer}
.r{display:flex;flex-wrap:wrap}input[type=range]{width:100%}#s{color:#aaa;font-size:13px;margin-top:12px}
</style></head><body><h1>Agent Dot</h1><div class="r">
<button style="background:#6b2fd6" onclick="s('working')">Working</button>
<button style="background:#d97a00" onclick="s('waiting')">Waiting</button>
<button style="background:#1f9d4a" onclick="s('done')">Done</button>
<button style="background:#c62828" onclick="s('error')">Error</button>
<button style="background:#1b6f80" onclick="s('idle')">Idle</button>
<button style="background:#333" onclick="s('off')">Off</button></div>
<p>Brightness <input type="range" min="0" max="%MAX%" id="b" onchange="fetch('/brightness?v='+this.value).then(u)"></p>
<p>Colour <input type="color" id="c" value="#ff00ff"> <button style="width:auto;padding:8px 14px;background:#444"
 onclick="fetch('/color?hex='+document.getElementById('c').value.slice(1)+'&anim=breathe').then(u)">Set</button></p>
<div id="s"></div><script>
function s(x){fetch('/state?s='+x).then(u)}
function u(){fetch('/status').then(r=>r.json()).then(j=>{document.getElementById('s').textContent=JSON.stringify(j);document.getElementById('b').value=j.brightness})}
u();setInterval(u,3000);
</script></body></html>)HTML";

static void sendJson(int code, const String &body) {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(code, "application/json", body);
}

static void handleState() {
  String s = server.hasArg("s") ? server.arg("s") : (server.hasArg("state") ? server.arg("state") : "");
  if (s.length() == 0 && server.hasArg("plain")) {               // POST body: plain text or {"state":"working"}
    s = server.arg("plain");
    int k = s.indexOf("\"state\"");
    if (k >= 0) { int a = s.indexOf('"', s.indexOf(':', k) + 1); int b = s.indexOf('"', a + 1); s = s.substring(a + 1, b); }
  }
  State st;
  uint64_t t = strtoull(server.arg("t").c_str(), nullptr, 10);
  if (stateFromName(s, st)) { agentSet(server.arg("sid"), st, 0, t); sendJson(200, statusJson()); }
  else if (runCommand(s, server.arg("sid"), "")) sendJson(200, statusJson());
  else sendJson(400, "{\"error\":\"unknown state\",\"valid\":[\"off\",\"idle\",\"working\",\"waiting\",\"done\",\"error\"]}");
}

// GET /s?c=working[&sid=abc][&t=<ms>]  - the fast path for hooks/scripts: tiny "ok" reply, no JSON building
static void handleShort() {
  String c = server.hasArg("c") ? server.arg("c") : server.arg("s");
  uint64_t t = strtoull(server.arg("t").c_str(), nullptr, 10);
  State st;
  bool ok = true;
  if (stateFromName(c, st)) agentSet(server.arg("sid"), st, 0, t);
  else ok = (c == "off") && runCommand(c, "", "");
  server.sendHeader("Connection", "close");
  server.send(ok ? 200 : 400, "text/plain", ok ? "ok\n" : "use c=working|waiting|input|done|error|idle|off\n");
}

static void handleColor() {
  if (runCommand("color", server.arg("hex"), server.arg("anim"))) sendJson(200, statusJson());
  else sendJson(400, "{\"error\":\"use /color?hex=RRGGBB&anim=solid|breathe|blink|chase\"}");
}

static void startNetwork() {
  if (MDNS.begin(HOSTNAME)) MDNS.addService("http", "tcp", 80);
  server.on("/", HTTP_GET, []() { String h(INDEX_HTML); h.replace("%MAX%", String(MAX_BRIGHTNESS)); server.send(200, "text/html", h); });
  server.on("/s", HTTP_ANY, handleShort);
  server.on("/state", HTTP_ANY, handleState);
  server.on("/staticip", HTTP_ANY, []() {                  // /staticip?ip=192.168.1.42&gw=192.168.1.1   or  ?ip=off
    if (runCommand("staticip", server.arg("ip"), server.arg("gw"))) sendJson(200, "{\"ok\":true,\"restarting\":true}");
    else sendJson(400, "{\"error\":\"use /staticip?ip=192.168.1.42&gw=192.168.1.1  or  ?ip=off\"}");
  });
  server.on("/color", HTTP_ANY, handleColor);
  server.on("/brightness", HTTP_ANY, []() { runCommand("brightness", server.arg("v"), ""); sendJson(200, statusJson()); });
  server.on("/status", HTTP_GET, []() { sendJson(200, statusJson()); });
  server.on("/reset-wifi", HTTP_GET, []() { sendJson(200, "{\"ok\":true}"); delay(200); runCommand("resetwifi", "", ""); });
  server.onNotFound([]() { sendJson(404, "{\"error\":\"not found\"}"); });
  server.begin();
  netReady = true;
  Serial.printf("[agentdot] online: http://%s.local  or  http://%s\n", HOSTNAME, WiFi.localIP().toString().c_str());
}

// ---------------------------------------------------------------- serial
static void handleSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      serialLine.trim();
      if (serialLine.length()) {
        String p[3]; int n = 0, start = 0;
        for (int i = 0; i <= (int)serialLine.length() && n < 3; i++) {
          if (i == (int)serialLine.length() || serialLine[i] == ' ') {
            if (i > start) p[n++] = serialLine.substring(start, i);
            start = i + 1;
          }
        }
        if (!runCommand(p[0], p[1], p[2]))
          Serial.println("[agentdot] commands: off idle working waiting done error | color RRGGBB [solid|breathe|blink|chase] | brightness N | status | staticip IP GATEWAY | staticip off | resetwifi");
      }
      serialLine = "";
    } else if (serialLine.length() < 64) {
      serialLine += c;
    }
  }
}

// ---------------------------------------------------------------- power
// Modem sleep is always on. After IDLE_DARK_AFTER_MS of nothing, the radio switches to deeper modem
// sleep (it still hears every request, ~0.1-0.3 s later); the next request switches it straight back.
static bool radioDeep = false;

static void powerLoop() {
  bool quiet = (state == ST_IDLE || state == ST_OFF) && IDLE_DARK_AFTER_MS > 0 &&
               (millis() - lastUpdate > IDLE_DARK_AFTER_MS);
  if (netReady && WiFi.status() == WL_CONNECTED && quiet != radioDeep) {
    radioDeep = quiet;
    WiFi.setSleep(quiet ? WIFI_PS_MAX_MODEM : WIFI_PS_MIN_MODEM);
    Serial.printf("[agentdot] radio: %s\n", quiet ? "deep modem sleep (quiet)" : "fast modem sleep (active)");
  }
#if DEEP_SLEEP_AFTER_MIN > 0
  if ((state == ST_IDLE || state == ST_OFF) && millis() - lastUpdate > (uint32_t)DEEP_SLEEP_AFTER_MIN * 60000UL) {
    Serial.println("[agentdot] no news for a long time - deep sleep (switch off/on or press the wake button)");
    strip.clear(); strip.show();
    delay(50);
#if WAKE_PIN >= 0
    pinMode(WAKE_PIN, INPUT_PULLUP);
#if CONFIG_IDF_TARGET_ESP32C3
    esp_deep_sleep_enable_gpio_wakeup(1ULL << WAKE_PIN, ESP_GPIO_WAKEUP_GPIO_LOW);
#else
    esp_sleep_enable_ext0_wakeup((gpio_num_t)WAKE_PIN, 0);
#endif
#endif
    esp_deep_sleep_start();
  }
#endif
}

// ---------------------------------------------------------------- setup / loop
WiFiManagerParameter pIp("sip", "Fixed IP (optional, e.g. 192.168.1.42 - leave blank for automatic)", "", 16);
WiFiManagerParameter pGw("sgw", "Router / gateway IP (needed with a fixed IP, e.g. 192.168.1.1)", "", 16);

void setup() {
  setCpuFrequencyMhz(CPU_MHZ);          // lower clock = lower current; Wi-Fi needs >= 80 MHz
  Serial.begin(115200);
  delay(200);

  prefs.begin("agentdot", false);
  brightness = prefs.getUChar("bright", DEFAULT_BRIGHTNESS);
  if (brightness > MAX_BRIGHTNESS) brightness = MAX_BRIGHTNESS;

  strip.begin();
  strip.setBrightness(brightness);
  strip.clear(); strip.show();
  stateSince = millis();

  WiFi.mode(WIFI_STA);
  WiFi.setHostname(HOSTNAME);
  WiFi.setTxPower(WIFI_POWER_8_5dBm);   // many C3 SuperMini boards only connect reliably at reduced TX power (and it saves power)
  WiFi.setSleep(WIFI_PS_MIN_MODEM);     // modem sleep: saves battery between requests, wakes every beacon
  WiFi.setAutoReconnect(true);

  IPAddress sip, sgw, smask;
  bool fixedIp = loadStaticIp(sip, sgw, smask);
  if (fixedIp) Serial.printf("[agentdot] fixed IP %s (gateway %s)\n", sip.toString().c_str(), sgw.toString().c_str());

  if (strlen(WIFI_SSID) > 0) {          // direct connection from secrets.h - no setup network needed
    if (fixedIp) WiFi.config(sip, sgw, smask, sgw);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    WiFi.setTxPower(WIFI_POWER_8_5dBm);
    Serial.printf("[agentdot] connecting to \"%s\"...\n", WIFI_SSID);
    setState(ST_SETUP);                 // blinks white until connected
    return;
  }

  // the setup page also asks for an optional fixed IP; it is saved in flash, never in the code
  if (fixedIp) { pIp.setValue(sip.toString().c_str(), 16); pGw.setValue(sgw.toString().c_str(), 16); }
  wm.addParameter(&pIp);
  wm.addParameter(&pGw);
  wm.setSaveConfigCallback([]() {
    String oldIp = prefs.isKey("sip") ? prefs.getString("sip", "") : String("");
    if (saveStaticIp(pIp.getValue(), pGw.getValue()) && oldIp != String(pIp.getValue())) restartAt = millis() + 1500;
  });
  if (fixedIp) wm.setSTAStaticIPConfig(sip, sgw, smask, sgw);

  wm.setConfigPortalBlocking(false);    // keep animating while the setup portal is open
  wm.setHostname(HOSTNAME);
  wm.setAPCallback([](WiFiManager *) {      // setup network just started: keep TX power low (SuperMini antennas)
    WiFi.setTxPower(WIFI_POWER_8_5dBm);
    Serial.printf("[agentdot] setup network \"%s\" is up at http://192.168.4.1\n", AP_NAME);
  });
  if (wm.autoConnect(AP_NAME)) {
    Serial.println("[agentdot] Wi-Fi connected");
  } else {
    Serial.printf("[agentdot] Wi-Fi setup: join \"%s\" and pick your network\n", AP_NAME);
    setState(ST_SETUP);
  }
}

void loop() {
  wm.process();                                         // runs the setup portal when it is open

  if (!netReady && WiFi.status() == WL_CONNECTED) {
    if (wm.getConfigPortalActive()) wm.stopConfigPortal();   // free port 80 for our own web server
    startNetwork();
    if (state == ST_SETUP) setState(ST_IDLE);
  }
  static uint32_t lastIpPrint = 0;                          // print the address every 30 s (handy in the Serial Monitor)
  if (millis() - lastIpPrint > 30000) {
    lastIpPrint = millis();
    if (WiFi.status() == WL_CONNECTED) Serial.printf("[agentdot] http://%s  (http://%s.local)\n", WiFi.localIP().toString().c_str(), HOSTNAME);
    else Serial.printf("[agentdot] not on Wi-Fi yet - join \"%s\" to set it up\n", AP_NAME);
  }
  if (netReady) { server.handleClient(); cloudLoop(); }

  handleSerial();

  if (millis() - lastFrame >= frameInterval()) {
    lastFrame = millis();
    renderFrame();
  }

  powerLoop();
  if (restartAt && (int32_t)(millis() - restartAt) >= 0) ESP.restart();

  delay(2);   // let the CPU idle between passes (big power saving, adds at most 2 ms of latency)
}
