#!/usr/bin/env bash
# One-time install of the launchd agent. Re-run to reinstall.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
command -v tmux >/dev/null || brew install tmux
mkdir -p "$HOME/Library/LaunchAgents"
sed "s|__HOME__|$HOME|g" "$REPO/launchd/com.alma.daemon.plist" > "$HOME/Library/LaunchAgents/com.alma.daemon.plist"
launchctl unload "$HOME/Library/LaunchAgents/com.alma.daemon.plist" 2>/dev/null || true
launchctl load "$HOME/Library/LaunchAgents/com.alma.daemon.plist"
echo "installed. watch:  tmux attach -t alma   |  status: cat $REPO/state/status.json"
echo "stop for good:     launchctl unload ~/Library/LaunchAgents/com.alma.daemon.plist; tmux kill-session -t alma"
