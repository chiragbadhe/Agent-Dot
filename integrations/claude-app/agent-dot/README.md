# Agent Dot for the Claude app

Agent Dot is a small RGB status light that clips to the top of a laptop screen. This plugin makes the light follow what Claude is doing in the Claude app:

- purple sweep while Claude works
- amber pulse when Claude asks you something or needs permission
- green when Claude finishes
- dim teal when idle

It sends a one-word status to a private ntfy.sh topic. The Agent Dot firmware (ESP32) listens to the same topic, so the light works from any Wi-Fi network. Setup needs ntfy.sh allowed in Claude's network settings (Settings → Capabilities), and the same CLOUD_TOPIC in the firmware as TOPIC in hooks/register.ts.
