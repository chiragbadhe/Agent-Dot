#!/usr/bin/env bash
# Builds AgentDotWatch and starts it at login (launchd).      macOS 13+
#   bash mac/install.sh [light-ip]      build + install + start
#   bash mac/install.sh --uninstall     stop + remove
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.agentdot.watch"
APP="$HOME/Applications/AgentDotWatch.app"
BIN="$APP/Contents/MacOS/AgentDotWatch"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/AgentDotWatch.log"
UIDN="$(id -u)"

launchctl bootout "gui/$UIDN/$LABEL" 2>/dev/null || true

if [ "$1" = "--uninstall" ]; then
  rm -f "$PLIST"; rm -rf "$APP"
  echo "Removed. You can also remove AgentDotWatch from System Settings > Privacy & Security > Accessibility."
  exit 0
fi

command -v swiftc >/dev/null || { echo "Needs the Xcode command line tools: xcode-select --install"; exit 1; }

mkdir -p "$HOME/.agentdot" "$APP/Contents/MacOS" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
if [ -n "$1" ]; then echo "$1" > "$HOME/.agentdot/host"; fi

# Rebuild only when the source changed: macOS ties the Accessibility permission to the exact binary,
# so an unnecessary rebuild would make you grant it again.
SUM="$(shasum -a 256 "$HERE/AgentDotWatch.swift" | cut -d' ' -f1)"
REBUILT=0
if [ -x "$BIN" ] && [ "$(cat "$APP/Contents/Resources/source.sha256" 2>/dev/null)" = "$SUM" ]; then
  echo "AgentDotWatch is up to date - not rebuilding (keeps your Accessibility permission)."
else
  echo "Building..."
  swiftc -O "$HERE/AgentDotWatch.swift" -o "$BIN"
  mkdir -p "$APP/Contents/Resources"
  echo "$SUM" > "$APP/Contents/Resources/source.sha256"
  REBUILT=1
fi

# A tiny background-only app bundle: gives the permission prompts a proper name
# (Accessibility, Local Network) and keeps it out of the Dock.
if [ "$REBUILT" = 1 ] || [ ! -f "$APP/Contents/Info.plist" ]; then
cat > "$APP/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleIdentifier</key><string>com.agentdot.watch</string>
  <key>CFBundleName</key><string>AgentDotWatch</string>
  <key>CFBundleExecutable</key><string>AgentDotWatch</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSUIElement</key><true/>
  <key>NSLocalNetworkUsageDescription</key><string>Sends Claude's status to your Agent Dot light on this network.</string>
</dict></plist>
EOF
fi
[ "$REBUILT" = 1 ] && { codesign --force --sign - --identifier "$LABEL" "$APP" >/dev/null 2>&1 || true; }

sed -e "s|__BIN__|$BIN|g" -e "s|__LOG__|$LOG|g" "$HERE/$LABEL.plist" > "$PLIST"
launchctl bootstrap "gui/$UIDN" "$PLIST"
launchctl kickstart -k "gui/$UIDN/$LABEL"

cat <<EOF

AgentDotWatch is running and will start at every login.

One-time permissions (macOS asks for these; if it doesn't, add them by hand):
  1. System Settings > Privacy & Security > Accessibility  -> turn on AgentDotWatch
     ($APP)
  2. Allow "AgentDotWatch" to find devices on your local network when asked.
The watcher picks up the Accessibility permission by itself within a second - no restart needed.

Check the labels it looks for:   "$BIN" --dump      (with the Claude app open)
Log:                             tail -f "$LOG"
Note: after a rebuild, remove AgentDotWatch from the Accessibility list and add it again (macOS treats it as a new app).
EOF
