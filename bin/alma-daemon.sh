#!/usr/bin/env bash
# bin/alma-daemon.sh -- keep Alma alive.
#
# Runs under launchd (KeepAlive). Keeps a tmux session named "alma" running
# `claude --chrome --model opus` in the repo; on (re)start, sends /loop plus
# prompts/cycle.md; writes state/status.json every minute.
#
# Known constraint: the Claude-in-Chrome extension binds to ONE client. Quit the
# Claude Desktop app while this daemon runs, or the terminal session will not
# get the browser. Chrome must be open on Alma's profile.
set -u
REPO="${ALMA_REPO:-$HOME/collective-state}"
SESSION="alma"
MODEL="${ALMA_MODEL:-opus}"
CLAUDE_BIN="${CLAUDE_BIN:-$(command -v claude || echo /opt/homebrew/bin/claude)}"
TMUX="${TMUX_BIN:-$(command -v tmux || echo /opt/homebrew/bin/tmux)}"
STATUS="$REPO/state/status.json"
LOG="$REPO/state/daemon.log"

log(){ printf '%s %s\n' "$(date +%FT%T%z)" "$*" >> "$LOG"; }

write_status(){
  local awake="$1" reason="${2:-}"
  local pid; pid="$($TMUX list-panes -t "$SESSION" -F '#{pane_pid}' 2>/dev/null | head -1)"
  printf '{"awake": %s, "reason": "%s", "pid": "%s", "session": "%s", "updated": "%s"}\n' \
    "$awake" "$reason" "${pid:-}" "$SESSION" "$(date -u +%FT%TZ)" > "$STATUS"
}

start_session(){
  log "starting tmux session $SESSION"
  cd "$REPO" || { log "repo missing: $REPO"; exit 1; }
  "$TMUX" new-session -d -s "$SESSION" -c "$REPO" \
    "$CLAUDE_BIN --chrome --model $MODEL --dangerously-skip-permissions"
  sleep 12
  # send the loop prompt as one line (tmux send-keys handles it as literal text)
  local prompt; prompt="/loop $(tr '\n' ' ' < "$REPO/prompts/cycle.md")"
  "$TMUX" send-keys -t "$SESSION" -l "$prompt"
  sleep 1
  "$TMUX" send-keys -t "$SESSION" Enter
  write_status true "started"
}

while true; do
  if ! "$TMUX" has-session -t "$SESSION" 2>/dev/null; then
    start_session
  else
    # Alma writes state/status.json herself when she rests (awake:false).
    # The daemon only refreshes the heartbeat; it never infers her state from
    # words on screen (a journal line containing "resting" is not a nap).
    if [ -f "$STATUS" ] && grep -q '"awake": *false' "$STATUS"; then
      write_status false "resting"
    else
      write_status true "running"
    fi
  fi
  sleep 60
done
