#!/usr/bin/env sh
set -eu

CURRENT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SCRIPT="$CURRENT_DIR/scripts/tmux-better-copy-buffer.sh"
. "$CURRENT_DIR/scripts/lib/tmux.sh"

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

bind_keys=$(tmux_bcb_option "@better-copy-buffer-bind-keys" "on")
ui=$(tmux_bcb_option "@better-copy-buffer-ui" "tui")
choose_key=$(tmux_bcb_option "@better-copy-buffer-choose-key" "=")
paste_key=$(tmux_bcb_option "@better-copy-buffer-paste-key" "]")
reverse_sort=$(tmux_bcb_option "@better-copy-buffer-reverse-sort" "off")
preview=$(tmux_bcb_option "@better-copy-buffer-preview" "on")
zoom=$(tmux_bcb_option "@better-copy-buffer-zoom" "off")
list_format=$(tmux_bcb_option "@better-copy-buffer-list-format" '#{buffer_sample}')
popup_width=$(tmux_bcb_option "@better-copy-buffer-popup-width" "95%")
popup_height=$(tmux_bcb_option "@better-copy-buffer-popup-height" "90%")
tui_preview=$(tmux_bcb_option "@better-copy-buffer-tui-preview" "on")
tui_layout=$(normalize_tui_layout "$(tmux_bcb_option "@better-copy-buffer-tui-layout" "")" "$tui_preview")
pins_db=$(expand_user_path "$(tmux_bcb_option "@better-copy-buffer-pins-db" "$(pins_db_default)")")
quoted_script=$(tmux_bcb_shell_word "$SCRIPT")
TUI="$CURRENT_DIR/scripts/tui.py"
quoted_tui=$(tmux_bcb_shell_word "$TUI")
quoted_tui_preview=$(tmux_bcb_shell_word "$tui_preview")
quoted_tui_layout=$(tmux_bcb_shell_word "$tui_layout")
quoted_pins_db=$(tmux_bcb_shell_word "$pins_db")
native_callback="run-shell \"$quoted_script paste-touch %%\""
popup_shell_command="printf '\033[?25l'; trap 'printf '\''\033[?25h'\''' EXIT; if [ \"\${TMUX_BCB_TUI:-}\" ]; then \"\$TMUX_BCB_TUI\" $quoted_script \"\$TMUX_BCB_TARGET\" $quoted_tui_preview $quoted_pins_db \"\${TMUX_BCB_TUI_LAYOUT:-$quoted_tui_layout}\" || $quoted_script choose \"\$TMUX_BCB_TARGET\"; elif [ \"\${TMUX_BCB_PYTHON:-}\" ]; then \"\$TMUX_BCB_PYTHON\" $quoted_tui $quoted_script \"\$TMUX_BCB_TARGET\" $quoted_tui_preview $quoted_pins_db \"\${TMUX_BCB_TUI_LAYOUT:-$quoted_tui_layout}\" || $quoted_script choose \"\$TMUX_BCB_TARGET\"; else python3 $quoted_tui $quoted_script \"\$TMUX_BCB_TARGET\" $quoted_tui_preview $quoted_pins_db \"\${TMUX_BCB_TUI_LAYOUT:-$quoted_tui_layout}\" || python $quoted_tui $quoted_script \"\$TMUX_BCB_TARGET\" $quoted_tui_preview $quoted_pins_db \"\${TMUX_BCB_TUI_LAYOUT:-$quoted_tui_layout}\" || $quoted_script choose \"\$TMUX_BCB_TARGET\"; fi"
popup_tmux_command="display-popup -E -w $(tmux_bcb_shell_word "$popup_width") -h $(tmux_bcb_shell_word "$popup_height") -e TMUX_BCB_TARGET=#{pane_id} -e TMUX_BCB_STATUS_STYLE=#{status-style} -e TMUX_BCB_TUI_LAYOUT=#{@better-copy-buffer-tui-layout} $(tmux_bcb_shell_word "$popup_shell_command")"

if [ "$bind_keys" = "on" ]; then
  choose_flags=""
  if [ "$zoom" = "on" ]; then
    choose_flags="$choose_flags -Z"
  fi
  if [ "$preview" != "on" ]; then
    choose_flags="$choose_flags -N"
  fi
  if [ "$reverse_sort" = "on" ]; then
    choose_flags="$choose_flags -r"
  fi
  if [ "$ui" = "native" ]; then
    tmux_bcb_tmux bind-key "$choose_key" choose-buffer $choose_flags -O time -F "$list_format" -f '#{m/r:^buffer[0-9]+$,#{buffer_name}}' "$native_callback"
  else
    tmux_bcb_tmux bind-key "$choose_key" run-shell -b -C "$popup_tmux_command"
  fi
  tmux_bcb_tmux bind-key "$paste_key" run-shell -b "$quoted_script paste-latest"
fi
