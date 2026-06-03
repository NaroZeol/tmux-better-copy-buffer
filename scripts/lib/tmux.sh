#!/usr/bin/env sh

tmux_bcb_tmux() {
  if [ "${TMUX_BCB_SOCKET:-}" ]; then
    tmux -S "$TMUX_BCB_SOCKET" "$@"
  else
    tmux "$@"
  fi
}

tmux_bcb_option() {
  option=$1
  default=$2
  value=$(tmux_bcb_tmux show-option -gqv "$option" 2>/dev/null || true)

  if [ "$value" ]; then
    printf '%s\n' "$value"
  else
    printf '%s\n' "$default"
  fi
}

tmux_bcb_message() {
  if [ "$(tmux_bcb_option "@better-copy-buffer-display-messages" "on")" != "on" ]; then
    return 0
  fi

  tmux_bcb_tmux display-message "$@" >/dev/null 2>&1 || true
}
