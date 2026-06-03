#!/usr/bin/env sh
set -eu

CURRENT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SCRIPT="$CURRENT_DIR/scripts/tmux-better-copy-buffer.sh"
. "$CURRENT_DIR/scripts/lib/tmux.sh"

bind_keys=$(tmux_bcb_option "@better-copy-buffer-bind-keys" "on")
choose_key=$(tmux_bcb_option "@better-copy-buffer-choose-key" "=")
paste_key=$(tmux_bcb_option "@better-copy-buffer-paste-key" "]")

if [ "$bind_keys" = "on" ]; then
  tmux_bcb_tmux bind-key "$choose_key" run-shell -b "$SCRIPT choose"
  tmux_bcb_tmux bind-key "$paste_key" run-shell -b "$SCRIPT paste-latest"
fi
