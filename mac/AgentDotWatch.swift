// AgentDotWatch - shows the Claude desktop app's state on Agent Dot.
//
// Watches the Claude app through the macOS Accessibility API. While Claude is answering, the chat
// shows a "Stop" button; this watcher sends `working` when it appears and `done` when it goes away.
// When Claude asks you something instead (a permission prompt with Allow / Deny buttons, a question
// with Submit / Skip), it sends `waiting` (amber).
// Only state changes are sent. Requests are fire-and-forget with short timeouts, so an offline
// light never blocks anything.
//
// Cheap by design: after the first scan it remembers where the message box is and re-checks only
// that small part of the window every 200 ms. A full window scan runs at most every few seconds.
//
//   swiftc -O AgentDotWatch.swift -o AgentDotWatch      (mac/install.sh does this for you)
//   ./AgentDotWatch -v        verbose: log every state change
//   ./AgentDotWatch --dump    list every button the Claude window exposes (to check the labels)
//
// Settings (environment variables, or files in ~/.agentdot/):
//   AGENTDOT_HOST         light IP or name   (default: ~/.agentdot/host, then agentdot.local)
//   AGENTDOT_STOP_LABELS  comma-separated button labels meaning "Claude is answering"
//   AGENTDOT_INPUT_LABELS comma-separated button labels meaning "Claude needs you" (prefix match)
//   AGENTDOT_APP_IDS      bundle ids to watch (default com.anthropic.claudefordesktop)
//
// MIT License - Agent Dot contributors

import AppKit
import ApplicationServices
import Foundation

// MARK: - settings

let env = ProcessInfo.processInfo.environment
let args = CommandLine.arguments
let verbose = args.contains("-v") || args.contains("--verbose")
let dumpMode = args.contains("--dump")

func confFile(_ name: String) -> String? {
    let p = NSHomeDirectory() + "/.agentdot/" + name
    guard let s = try? String(contentsOfFile: p, encoding: .utf8) else { return nil }
    let t = s.trimmingCharacters(in: .whitespacesAndNewlines)
    return t.isEmpty ? nil : t
}
func list(_ s: String) -> [String] {
    s.lowercased().split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
}

let host = env["AGENTDOT_HOST"] ?? confFile("host") ?? "agentdot.local"
let fallbackHost = "agentdot.local"
let appIDs = Set(list(env["AGENTDOT_APP_IDS"] ?? confFile("app_ids") ?? "com.anthropic.claudefordesktop"))
let stopLabels = Set(list(env["AGENTDOT_STOP_LABELS"] ?? confFile("stop_labels") ?? "stop response,stop generating,stop"))
let sendLabels = Set(list(env["AGENTDOT_SEND_LABELS"] ?? confFile("send_labels") ?? "send message,send"))
// Buttons that mean "Claude is asking you something" (permission prompts, questions). Prefix match:
// "allow" also covers "allow once" / "allow for this chat". Check yours with --dump while a prompt is open.
let inputLabels = Set(list(env["AGENTDOT_INPUT_LABELS"] ?? confFile("input_labels") ??
    "allow,always allow,deny,don't allow,do not allow,decline,approve,reject,skip,submit"))
let sessionID = "app"                  // the light keeps this separate from Claude Code sessions

let pollInterval = 0.2                 // seconds
let fullScanIdle = 3.0                 // full window scan at most this often while idle...
let fullScanBusy = 1.0                 // ...and while working
let fullScanBudget = 6000              // max elements visited per window in a full scan
let keepAliveEvery = 300.0             // re-send the state every 5 min during long answers / waits
let inputWindow = 800                  // look for prompt buttons only this far from the bottom of the page
let inputScanBusy = 2.0                // while working, also check for a prompt this often
let inputScanWaiting = 1.0             // while waiting on you, re-check the prompt this often
let afterAnswerGrace = 20.0            // after you answer a prompt, wait up to this long for Claude to resume
let unknownTimeout = 600.0             // Claude out of sight this long while working -> back to idle
let doneDelay = 2.5                    // Stop must stay gone this long before "done" (no green flashes between steps)

func log(_ s: String) {
    let f = DateFormatter(); f.dateFormat = "HH:mm:ss.SSS"
    FileHandle.standardError.write("\(f.string(from: Date())) [agentdot] \(s)\n".data(using: .utf8)!)
}

// MARK: - sending (fire-and-forget)

let session: URLSession = {
    let c = URLSessionConfiguration.ephemeral
    c.timeoutIntervalForRequest = 1.5
    c.timeoutIntervalForResource = 2.5
    c.waitsForConnectivity = false
    c.httpMaximumConnectionsPerHost = 2
    return URLSession(configuration: c)
}()

func send(_ state: String) {
    let t = UInt64(Date().timeIntervalSince1970 * 1000)     // lets the light drop requests that arrive late
    let q = "/s?c=\(state)&sid=\(sessionID)&t=\(t)"
    // Try the saved IP, retry it once (a weak signal or a light waking from modem sleep can drop
    // the first packet), then fall back to agentdot.local. Never blocks the watcher.
    let plan: [(String, Double, Double)] = [(host, 1.5, 0), (host, 2.0, 0.3), (fallbackHost, 2.5, 0.3)]
    func attempt(_ i: Int) {
        guard i < plan.count else { if verbose { log("light not reachable - gave up on \(state)") }; return }
        let (h, timeout, delay) = plan[i]
        if i == 2 && h == host { attempt(i + 1); return }     // no separate fallback if host already is agentdot.local
        guard let url = URL(string: "http://\(h)\(q)") else { return }
        var r = URLRequest(url: url)
        r.timeoutInterval = timeout
        DispatchQueue.global().asyncAfter(deadline: .now() + delay) {
            session.dataTask(with: r) { _, resp, err in
                if err != nil || (resp as? HTTPURLResponse)?.statusCode != 200 {
                    if verbose { log("\(state): no reply from \(h) (\(err?.localizedDescription ?? "bad reply")), retrying") }
                    attempt(i + 1)
                }
            }.resume()
        }
    }
    attempt(0)
    if verbose { log("-> \(state)") }
}

// MARK: - accessibility helpers

let kRole = kAXRoleAttribute as String
let kDesc = kAXDescriptionAttribute as String
let kTitle = kAXTitleAttribute as String
let kChildren = kAXChildrenAttribute as String
let kEnabled = kAXEnabledAttribute as String
let wanted = [kRole, kDesc, kTitle, kChildren, kEnabled] as CFArray

struct Node { let role: String; let label: String; let enabled: Bool; let children: [AXUIElement] }

/// One IPC round trip per element: role, description, title, children, enabled. nil = element gone.
func node(_ e: AXUIElement) -> Node? {
    var out: CFArray?
    let err = AXUIElementCopyMultipleAttributeValues(e, wanted, AXCopyMultipleAttributeOptions(rawValue: 0), &out)
    guard err == .success, let arr = out as? [AnyObject], arr.count == 5 else { return nil }
    func str(_ v: AnyObject) -> String? { (CFGetTypeID(v) == CFStringGetTypeID()) ? (v as! String) : nil }
    let role = str(arr[0]) ?? ""
    let label = (str(arr[1]).flatMap { $0.isEmpty ? nil : $0 } ?? str(arr[2]) ?? "")
        .lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
    var kids: [AXUIElement] = []
    if CFGetTypeID(arr[3]) == CFArrayGetTypeID(), let k = arr[3] as? [AXUIElement] { kids = k }
    var enabled = true
    if let b = arr[4] as? Bool { enabled = b }
    return Node(role: role, label: label, enabled: enabled, children: kids)
}

/// "allow" matches "allow", "allow once", "allow for this chat" - but not "allowance".
func matches(_ label: String, _ set: Set<String>) -> Bool {
    if set.contains(label) { return true }
    for l in set where label.hasPrefix(l + " ") { return true }
    return false
}

// Leaf-ish roles that never contain the buttons we look for: don't descend into them.
let skipRoles: Set<String> = ["AXStaticText", "AXImage", "AXHeading", "AXLink", "AXTextArea", "AXTextField", "AXList", "AXTable"]

struct ScanResult { var stop = false; var send = false; var input = false; var composer: AXUIElement? }

/// Depth-first, bottom of the page first (the message box and any permission prompt sit at the end).
///   lookForInput: also look for Allow / Deny / ... buttons among the first `inputWindow` elements
///                 visited (the bottom of the page), and don't stop early at the Stop button.
func scan(_ root: AXUIElement, budget: Int, lookForInput: Bool = false) -> ScanResult? {
    guard node(root) != nil else { return nil }
    var res = ScanResult()
    var stack: [(AXUIElement, AXUIElement?, AXUIElement?)] = [(root, nil, nil)]   // element, parent, grandparent
    var visited = 0
    var limit = budget
    while visited < limit, let item = stack.popLast() {
        let (e, parent, grand) = item
        visited += 1
        guard let n = node(e) else { continue }
        if n.role == "AXButton" {
            if lookForInput && !res.input && visited <= inputWindow && n.enabled && matches(n.label, inputLabels) {
                res.input = true
                if res.stop || res.send { return res }
            }
            if stopLabels.contains(n.label) {
                res.stop = true; res.composer = grand ?? parent
                if !lookForInput || res.input { return res }
                limit = min(limit, inputWindow)
            } else if sendLabels.contains(n.label) && !res.send {
                res.send = true; res.composer = grand ?? parent
                if lookForInput && res.input { return res }
                limit = min(limit, lookForInput ? max(inputWindow, visited + 300) : visited + 1500)
            }
            continue
        }
        if skipRoles.contains(n.role) { continue }
        for c in n.children { stack.append((c, e, parent)) }      // last child is popped first
    }
    return res
}

func dumpButtons(_ root: AXUIElement) {
    var stack = [root]; var seen = 0
    while let e = stack.popLast(), seen < 50000 {
        seen += 1
        guard let n = node(e) else { continue }
        if n.role == "AXButton" {
            var tag = ""
            if stopLabels.contains(n.label) { tag = "   <- STOP (working)" }
            else if sendLabels.contains(n.label) { tag = "   <- SEND (message box)" }
            else if matches(n.label, inputLabels) { tag = "   <- INPUT (needs you)" }
            print("button: \"\(n.label)\"\(n.enabled ? "" : " (disabled)")\(tag)")
        }
        stack.append(contentsOf: n.children)      // bottom of the page first, like the watcher
    }
    print("(\(seen) elements)")
}

// MARK: - watcher

enum Phase: String { case idle, working, waiting }

final class Watcher {
    var pid: pid_t = 0
    var appEl: AXUIElement?
    var composers: [AXUIElement] = []
    var lastFullScan = Date.distantPast
    var lastInputScan = Date.distantPast
    var phase = Phase.idle
    var lastStop = false
    var lastInput = false
    var missSince: Date?
    var graceUntil: Date?
    var unknownSince: Date?
    var lastSent = Date.distantPast
    var warnedTrust = false

    func claudeApp() -> NSRunningApplication? {
        NSWorkspace.shared.runningApplications.first { app in
            if let id = app.bundleIdentifier?.lowercased(), appIDs.contains(id) { return true }
            return false
        }
    }

    func windows(_ app: AXUIElement) -> [AXUIElement] {
        var v: CFTypeRef?
        guard AXUIElementCopyAttributeValue(app, kAXWindowsAttribute as CFString, &v) == .success,
              let w = v as? [AXUIElement] else { return [] }
        return w
    }

    /// Claude windows on the current Space that aren't minimized (other Spaces aren't listed at all).
    func visibleWindows(_ app: AXUIElement) -> [AXUIElement] {
        windows(app).filter { w in
            var v: CFTypeRef?
            if AXUIElementCopyAttributeValue(w, kAXMinimizedAttribute as CFString, &v) == .success, let m = v as? Bool { return !m }
            return true
        }
    }

    /// (Stop button visible, Claude is asking you something)
    /// known = false when no Claude message box is visible to us (window on another Space or desktop,
    /// minimized, closed): then nothing can be concluded and the light keeps its colour.
    func observe(_ app: AXUIElement) -> (stop: Bool, input: Bool, known: Bool) {
        let now = Date()
        // fast path: only the remembered message-box area(s), ~10-50 elements
        var valid = false
        var stop = false
        composers = composers.filter { c in
            guard let r = scan(c, budget: 300) else { return false }    // element gone (navigation, reload)
            valid = true
            if r.stop { stop = true }
            return true
        }

        // Look for a permission prompt / question when Claude stops showing Stop mid-task, regularly
        // while waiting on you, and every few seconds while working (in case Stop stays visible).
        let wantInput = (phase == .working && !stop && now.timeIntervalSince(lastInputScan) >= 0.5) ||
                        (phase == .waiting && now.timeIntervalSince(lastInputScan) >= inputScanWaiting) ||
                        (phase == .working && now.timeIntervalSince(lastInputScan) >= inputScanBusy)
        let every = phase == .idle ? fullScanIdle : fullScanBusy
        let wantFull = wantInput || !valid || now.timeIntervalSince(lastFullScan) >= every
        let keepInput = lastInput && phase == .waiting        // between checks, a prompt counts as still open
        if !wantFull { return (stop, keepInput, stop || keepInput || !visibleWindows(app).isEmpty) }
        if !valid && !wantInput && now.timeIntervalSince(lastFullScan) < 0.5 { return (lastStop, lastInput, false) }  // don't hammer when lost

        // full scan of every window (also refreshes the remembered areas)
        lastFullScan = now
        if wantInput { lastInputScan = now }
        var found: [AXUIElement] = []
        var input = false
        let wins = visibleWindows(app)
        for w in wins {
            guard let r = scan(w, budget: fullScanBudget, lookForInput: wantInput) else { continue }
            if let c = r.composer { found.append(c) }
            if r.stop { stop = true }
            if r.input { input = true }
        }
        // Windows on another Space aren't listed, but message boxes we already know usually still answer:
        // keep them rather than forgetting them.
        if !found.isEmpty { composers = found }
        if !wantInput { input = keepInput }
        return (stop, input, stop || input || !wins.isEmpty)
    }

    func go(_ p: Phase, _ msg: String) {
        if p != phase || Date().timeIntervalSince(lastSent) > keepAliveEvery {
            phase = p; lastSent = Date(); send(msg)
        }
    }

    func update(stop: Bool, input: Bool, known: Bool) {
        lastStop = stop; lastInput = input
        let now = Date()
        if !input && !stop && !known {
            // Can't see Claude right now (you switched Space / desktop, or the window is minimized).
            // Keep the current colour; only give up after unknownTimeout.
            missSince = nil
            if unknownSince == nil { unknownSince = now }
            if phase != .idle, now.timeIntervalSince(unknownSince!) >= unknownTimeout {
                phase = .idle; unknownSince = nil; lastSent = now; send("idle")
            }
            return
        }
        unknownSince = nil
        if input { missSince = nil; go(.waiting, "waiting"); return }   // a question / permission prompt wins
        if stop  { missSince = nil; graceUntil = nil; go(.working, "working"); return }
        if phase == .idle { return }
        if phase == .waiting {
            // The prompt went away without a Stop button: you answered it, and Claude is about to
            // continue. Show purple right away and give Claude time to start again.
            missSince = nil; graceUntil = now.addingTimeInterval(afterAnswerGrace)
            go(.working, "working"); return
        }
        if let g = graceUntil, now < g { return }
        // Claude briefly hides the Stop button between steps. Only call it "done" once nothing has
        // shown for doneDelay seconds.
        if missSince == nil { missSince = now }
        if now.timeIntervalSince(missSince!) >= doneDelay {
            phase = .idle; missSince = nil; graceUntil = nil; lastSent = now; send("done")
        }
    }

    func tick() {
        guard AXIsProcessTrusted() else {
            if !warnedTrust { log("waiting for Accessibility permission (System Settings > Privacy & Security > Accessibility)"); warnedTrust = true }
            return
        }
        guard let app = claudeApp() else {
            if appEl != nil { if phase != .idle { phase = .idle; send("idle") }; appEl = nil; composers = []; if verbose { log("Claude app closed") } }
            return
        }
        if app.processIdentifier != pid || appEl == nil {
            pid = app.processIdentifier
            let el = AXUIElementCreateApplication(pid)
            // Electron apps only expose their web content after this flag is set.
            AXUIElementSetAttributeValue(el, "AXManualAccessibility" as CFString, kCFBooleanTrue)
            AXUIElementSetMessagingTimeout(el, 0.5)
            appEl = el; composers = []; lastFullScan = .distantPast
            if verbose { log("watching Claude (pid \(pid)), light at \(host)") }
        }
        let o = observe(appEl!)
        update(stop: o.stop, input: o.input, known: o.known)
    }
}

// MARK: - main

let promptKey = kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String
_ = AXIsProcessTrustedWithOptions([promptKey: true] as CFDictionary)   // shows the permission prompt once

if dumpMode {
    let w = Watcher()
    guard AXIsProcessTrusted() else { print("Grant Accessibility permission first, then run again."); exit(1) }
    guard let app = w.claudeApp() else { print("The Claude app isn't running."); exit(1) }
    let el = AXUIElementCreateApplication(app.processIdentifier)
    AXUIElementSetAttributeValue(el, "AXManualAccessibility" as CFString, kCFBooleanTrue)
    Thread.sleep(forTimeInterval: 1.0)       // give Chromium a moment to build its accessibility tree
    for win in w.windows(el) { dumpButtons(win) }
    print("stop labels: \(stopLabels.sorted())\nsend labels: \(sendLabels.sorted())\ninput labels: \(inputLabels.sorted())")
    exit(0)
}

// Keep macOS from App-Napping us (that would stretch the 200 ms timer to seconds).
let activity = ProcessInfo.processInfo.beginActivity(options: [.userInitiatedAllowingIdleSystemSleep], reason: "Agent Dot status polling")
AXUIElementSetMessagingTimeout(AXUIElementCreateSystemWide(), 0.5)

let watcher = Watcher()
send("idle")                                   // clear anything left over from a previous run
let timer = Timer(timeInterval: pollInterval, repeats: true) { _ in watcher.tick() }
timer.tolerance = 0.03
RunLoop.main.add(timer, forMode: .common)
log("started - light at \(host)\(verbose ? "" : " (use -v to log state changes)")")
withExtendedLifetime(activity) { RunLoop.main.run() }
