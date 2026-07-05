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

tmux_bcb_shell_word() {
  value=${1-}

  case $value in
    '')
      printf "''"
      ;;
    *[!abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_./%+=:@,-]*)
      printf "'%s'" "$(printf '%s\n' "$value" | sed "s/'/'\\\\''/g")"
      ;;
    *)
      printf '%s' "$value"
      ;;
  esac
}

pins_db_default() {
  if [ "${XDG_DATA_HOME:-}" ]; then
    data_home=$XDG_DATA_HOME
  elif [ "${HOME:-}" ]; then
    data_home=$HOME/.local/share
  else
    data_home=${TMPDIR:-/tmp}
  fi

  printf '%s\n' "$data_home/tmux-better-copy-buffer/pins.sqlite3"
}

expand_user_path() {
  value=$1

  case $value in
    "~")
      printf '%s\n' "${HOME:-$value}"
      ;;
    "~/"*)
      printf '%s/%s\n' "${HOME:-~}" "${value#~/}"
      ;;
    *)
      printf '%s\n' "$value"
      ;;
  esac
}

tui_layout_from_preview() {
  if [ "${1:-}" = "on" ]; then
    printf '%s\n' "both"
  else
    printf '%s\n' "none"
  fi
}

normalize_tui_layout() {
  layout=${1:-}
  preview=${2:-on}

  case $layout in
    both | preview | pins | none)
      printf '%s\n' "$layout"
      ;;
    *)
      tui_layout_from_preview "$preview"
      ;;
  esac
}

current_tui_layout() {
  preview=${1:-on}
  layout=$(tmux_bcb_option "@better-copy-buffer-tui-layout" "")
  normalize_tui_layout "$layout" "$preview"
}

paste_touch() {
  buffer=${1:-}
  target_pane=${2:-}
  strategy=$(recency_strategy) || return

  if ! is_auto_buffer_name "$buffer"; then
    tmux_bcb_message "tmux-better-copy-buffer: unsupported buffer name: $buffer"
    return 2
  fi

  if [ "$target_pane" ]; then
    tmux_bcb_tmux paste-buffer -t "$target_pane" -b "$buffer"
  else
    tmux_bcb_tmux paste-buffer -b "$buffer"
  fi
  refresh_recency "$buffer" "$strategy"
}

paste_text_file() {
  file=${1:-}
  target_pane=${2:-}

  if [ ! -r "$file" ]; then
    tmux_bcb_message "tmux-better-copy-buffer: pin file not readable"
    return 2
  fi

  buffer="tmux-bcb-pin-$$"
  tmux_bcb_tmux load-buffer -b "$buffer" "$file" || return

  status=0
  if [ "$target_pane" ]; then
    tmux_bcb_tmux paste-buffer -t "$target_pane" -b "$buffer" || status=$?
  else
    tmux_bcb_tmux paste-buffer -b "$buffer" || status=$?
  fi
  tmux_bcb_tmux delete-buffer -b "$buffer" >/dev/null 2>&1 || true
  if [ "$status" -eq 0 ]; then
    tmux_bcb_tmux load-buffer "$file" >/dev/null 2>&1 || true
  fi
  return "$status"
}

recency_strategy() {
  strategy=$(tmux_bcb_option "@better-copy-buffer-recency-strategy" "touch")
  case $strategy in
    touch | recreate)
      printf '%s\n' "$strategy"
      ;;
    *)
      tmux_bcb_message "tmux-better-copy-buffer: unsupported recency strategy: $strategy"
      return 2
      ;;
  esac
}

refresh_recency() {
  buffer=$1
  strategy=$2
  tmp=$(mktemp "${TMPDIR:-/tmp}/tmux-better-copy-buffer.XXXXXX")
  trap 'rm -f "$tmp"' EXIT HUP INT TERM

  tmux_bcb_tmux save-buffer -b "$buffer" "$tmp"

  case $strategy in
    touch)
      tmux_bcb_tmux load-buffer -b "$buffer" "$tmp"
      ;;
    recreate)
      tmux_bcb_tmux load-buffer "$tmp"
      tmux_bcb_tmux delete-buffer -b "$buffer"
      ;;
  esac
}

auto_buffer_filter='#{m/r:^buffer[0-9]+$,#{buffer_name}}'

normalize_tui_rows() {
  awk '
    BEGIN { FS = "\t"; OFS = "\t" }
    {
      created = $1
      name = $2
      sample = $0
      sub(/^[^\t]*\t[^\t]*\t?/, "", sample)
      gsub(/\\t/, "    ", sample)
      gsub(/\t/, "    ", sample)
      gsub(/\r/, " ", sample)
      if (sample == "") {
        sample = "<empty>"
      }
      print created, name, sample
    }
  '
}

list_tui_rows() {
  tmp=$(mktemp "${TMPDIR:-/tmp}/tmux-better-copy-buffer.XXXXXX") || return

  if tmux_bcb_tmux list-buffers -F '#{buffer_created}	#{buffer_name}	#{buffer_sample}' -f "$auto_buffer_filter" >"$tmp"; then
    if sort -rn -k 1,1 "$tmp" | normalize_tui_rows; then
      status=0
    else
      status=$?
    fi
  else
    status=$?
  fi

  rm -f "$tmp"
  return "$status"
}

preview_buffer() {
  buffer=${1:-}
  if ! is_auto_buffer_name "$buffer"; then
    return 2
  fi

  tmux_bcb_tmux show-buffer -b "$buffer"
}

delete_buffer() {
  buffer=${1:-}
  if ! is_auto_buffer_name "$buffer"; then
    tmux_bcb_message "tmux-better-copy-buffer: unsupported buffer name: $buffer"
    return 2
  fi

  tmux_bcb_tmux delete-buffer -b "$buffer"
}

file_ends_with_newline() {
  file=$1
  [ -s "$file" ] || return 1
  last_byte=$(tail -c 1 "$file" 2>/dev/null | od -An -tx1 | tr -d '[:space:]')
  [ "$last_byte" = "0a" ]
}

strip_final_byte() {
  file=$1
  size=$(wc -c <"$file" | tr -d '[:space:]')
  [ "$size" -gt 0 ] || return 0
  new_size=$((size - 1))

  if command_exists truncate; then
    truncate -s "$new_size" "$file"
    return
  fi

  tmp=$(mktemp "${TMPDIR:-/tmp}/tmux-better-copy-buffer.XXXXXX") || return
  if dd if="$file" of="$tmp" bs=1 count="$new_size" >/dev/null 2>&1; then
    mv "$tmp" "$file"
  else
    status=$?
    rm -f "$tmp"
    return "$status"
  fi
}

edit_buffer() {
  buffer=${1:-}
  if ! is_auto_buffer_name "$buffer"; then
    tmux_bcb_message "tmux-better-copy-buffer: unsupported buffer name: $buffer"
    return 2
  fi

  tmp=$(mktemp "${TMPDIR:-/tmp}/tmux-better-copy-buffer.XXXXXX") || return
  trap 'rm -f "$tmp"' EXIT HUP INT TERM

  tmux_bcb_tmux save-buffer -b "$buffer" "$tmp"
  had_final_newline=0
  if file_ends_with_newline "$tmp"; then
    had_final_newline=1
  fi
  editor=${VISUAL:-${EDITOR:-vi}}
  if sh -c "$editor \"\$1\"" sh "$tmp"; then
    if [ "$had_final_newline" -eq 0 ] && file_ends_with_newline "$tmp"; then
      strip_final_byte "$tmp" || return
    fi
    tmux_bcb_tmux load-buffer -b "$buffer" "$tmp"
  else
    status=$?
    rm -f "$tmp"
    return "$status"
  fi
}

set_buffer_file() {
  buffer=${1:-}
  file=${2:-}

  if ! is_auto_buffer_name "$buffer"; then
    tmux_bcb_message "tmux-better-copy-buffer: unsupported buffer name: $buffer"
    return 2
  fi
  if [ ! -r "$file" ]; then
    tmux_bcb_message "tmux-better-copy-buffer: buffer file not readable"
    return 2
  fi

  tmux_bcb_tmux load-buffer -b "$buffer" "$file"
}

python_command() {
  python_bin=${TMUX_BCB_PYTHON:-}

  if [ "$python_bin" ]; then
    command_exists "$python_bin" || return 1
    printf '%s\n' "$python_bin"
    return 0
  fi

  for candidate in python3 python; do
    if command_exists "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

choose_tui() {
  script_path=$0
  target_pane=${1:-}
  preview=$(tmux_bcb_option "@better-copy-buffer-tui-preview" "on")
  layout=$(current_tui_layout "$preview")
  pins_db=$(expand_user_path "$(tmux_bcb_option "@better-copy-buffer-pins-db" "$(pins_db_default)")")
  status_style=$(tmux_bcb_option "status-style" "")

  if [ "${TMUX_BCB_TUI:-}" ]; then
    TMUX_BCB_STATUS_STYLE=$status_style "$TMUX_BCB_TUI" "$script_path" "$target_pane" "$preview" "$pins_db" "$layout"
    return
  fi

  python_bin=$(python_command || true)
  if [ -z "$python_bin" ]; then
    tmux_bcb_message "tmux-better-copy-buffer: Python not found, using native chooser"
    choose_buffer "$target_pane" || return 0
    return
  fi

  TMUX_BCB_STATUS_STYLE=$status_style "$python_bin" "$SCRIPT_DIR/tui.py" "$script_path" "$target_pane" "$preview" "$pins_db" "$layout" && return

  tmux_bcb_message "tmux-better-copy-buffer: TUI failed, using native chooser"
  choose_buffer "$target_pane" || return 0
}

set_tui_layout() {
  layout=$(normalize_tui_layout "${1:-}" "on")
  tmux_bcb_tmux set-option -gq "@better-copy-buffer-tui-layout" "$layout"
}

choose_buffer() {
  script_path=$0
  target_pane=${1:-}
  list_format=$(tmux_bcb_option "@better-copy-buffer-list-format" '#{buffer_sample}')
  choose_flags=""
  if [ "$(tmux_bcb_option "@better-copy-buffer-zoom" "off")" = "on" ]; then
    choose_flags="$choose_flags -Z"
  fi
  if [ "$(tmux_bcb_option "@better-copy-buffer-preview" "on")" != "on" ]; then
    choose_flags="$choose_flags -N"
  fi
  if [ "$(tmux_bcb_option "@better-copy-buffer-reverse-sort" "off")" = "on" ]; then
    choose_flags="$choose_flags -r"
  fi

  callback_shell="$(tmux_bcb_shell_word "$script_path") paste-touch %%"
  if [ "$target_pane" ]; then
    callback_shell="$callback_shell $(tmux_bcb_shell_word "$target_pane")"
    tmux_bcb_tmux choose-buffer -t "$target_pane" $choose_flags -O time -F "$list_format" -f "$auto_buffer_filter" "run-shell \"$callback_shell\""
  else
    tmux_bcb_tmux choose-buffer $choose_flags -O time -F "$list_format" -f "$auto_buffer_filter" "run-shell \"$callback_shell\""
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

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

usage() {
  cat >&2 <<'USAGE'
usage: tmux-better-copy-buffer.sh <command>

commands:
  choose
  choose-tui
  delete <buffer>
  edit <buffer>
  list-tui-rows
  paste-latest
  paste-text-file <file>
  paste-touch <buffer>
  preview <buffer>
  set-buffer-file <buffer> <file>
  set-tui-layout <both|preview|pins|none>
USAGE
}

command=${1:-}
case "$command" in
  paste-touch)
    shift
    paste_touch "$@"
    ;;
  paste-text-file)
    shift
    paste_text_file "$@"
    ;;
  choose)
    shift
    choose_buffer "$@"
    ;;
  choose-tui)
    shift
    choose_tui "$@"
    ;;
  list-tui-rows)
    shift
    list_tui_rows "$@"
    ;;
  paste-latest)
    shift
    paste_latest "$@"
    ;;
  delete)
    shift
    delete_buffer "$@"
    ;;
  edit)
    shift
    edit_buffer "$@"
    ;;
  set-buffer-file)
    shift
    set_buffer_file "$@"
    ;;
  preview)
    shift
    preview_buffer "$@"
    ;;
  set-tui-layout)
    shift
    set_tui_layout "$@"
    ;;
  *)
    usage
    exit 2
    ;;
esac
