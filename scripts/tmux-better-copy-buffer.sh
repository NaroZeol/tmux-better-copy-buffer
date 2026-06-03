#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$SCRIPT_DIR/lib/tmux.sh"

is_auto_buffer_name() {
  name=${1:-}
  suffix=${name#buffer}

  if [ "$name" = "$suffix" ] || [ -z "$suffix" ]; then
    return 1
  fi

  case $suffix in
    *[!0-9]*) return 1 ;;
    *) return 0 ;;
  esac
}

paste_touch() {
  buffer=${1:-}

  if ! is_auto_buffer_name "$buffer"; then
    tmux_bcb_message "tmux-better-copy-buffer: unsupported buffer name: $buffer"
    return 2
  fi

  tmp=$(mktemp "${TMPDIR:-/tmp}/tmux-better-copy-buffer.XXXXXX")
  trap 'rm -f "$tmp"' EXIT HUP INT TERM

  tmux_bcb_tmux save-buffer -b "$buffer" "$tmp"
  tmux_bcb_tmux paste-buffer -b "$buffer"
  tmux_bcb_tmux load-buffer -b "$buffer" "$tmp"
}

choose_buffer() {
  script_path=$0
  if [ "$(tmux_bcb_option "@better-copy-buffer-reverse-sort" "off")" = "on" ]; then
    tmux_bcb_tmux choose-buffer -r -O time -f '#{m/r:^buffer[0-9]+$,#{buffer_name}}' "run-shell -b '$script_path paste-touch %%'"
  else
    tmux_bcb_tmux choose-buffer -O time -f '#{m/r:^buffer[0-9]+$,#{buffer_name}}' "run-shell -b '$script_path paste-touch %%'"
  fi
}

paste_latest() {
  buffer=$(tmux_bcb_tmux list-buffers -F '#{buffer_name}' 2>/dev/null | sed -n '1p')
  if [ -z "$buffer" ]; then
    tmux_bcb_message "tmux-better-copy-buffer: no buffers"
    return 1
  fi

  paste_touch "$buffer"
}

usage() {
  cat >&2 <<'USAGE'
usage: tmux-better-copy-buffer.sh <command>

commands:
  choose
  paste-latest
  paste-touch <buffer>
USAGE
}

command=${1:-}
case "$command" in
  paste-touch)
    shift
    paste_touch "$@"
    ;;
  choose)
    shift
    choose_buffer "$@"
    ;;
  paste-latest)
    shift
    paste_latest "$@"
    ;;
  *)
    usage
    exit 2
    ;;
esac
