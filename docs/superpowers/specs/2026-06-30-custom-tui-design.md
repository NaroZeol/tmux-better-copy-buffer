# Custom Popup TUI Design

## Goal

Replace the current default chooser with a plugin-owned popup TUI that keeps a
fast, compact, keyboard-first feel without depending on an external selector.

The chooser should stay focused on tmux paste buffers. It should not introduce a
separate clipboard history database or change `prefix ]` paste-latest behavior.
It may keep a small SQLite database for user-pinned common phrases, but only for
phrases explicitly pinned from the TUI.

## User Experience

`prefix =` opens a near-fullscreen tmux popup. The visual style should remain
compact and utilitarian:

- a compact prompt at the top;
- a single-column buffer sample list;
- the selected row marked clearly;
- an optional right pane split between current buffer content and pinned common
  phrases;
- no persistent key-hint footer during normal navigation.

Newest buffers are shown first. Buffer names such as `buffer1954` are internal
metadata and are not displayed as row titles.

Default controls:

- `j`: move selection down.
- `k`: move selection up.
- numeric prefixes such as `12j` and `3k`: jump by count for the next `j` or
  `k`.
- `/`: enter search mode.
- `Esc`: in search mode, leave search mode and return to normal mode; in normal
  mode, clear a pending numeric prefix.
- `Enter`: in search mode, commit the search and jump to the next match; in
  normal mode, paste the selected buffer into the invoking pane and refresh
  recency.
- `n`: jump to the next search match.
- `N`: jump to the previous search match.
- `p`: pin the selected buffer as a persistent common phrase.
- `Tab`: switch focus between the buffer list and pinned common phrases.
- `d`: delete the selected buffer and refresh the list.
- `e`: edit the selected buffer, then refresh the row and preview.
- `v`: toggle right pane visibility.
- `:help`: show the full key reference.
- `q`: close without pasting.

Search mode should behave like Vim search: it should not filter visible rows.
After typing a pattern and pressing `Enter`, the TUI returns to normal mode and
moves the selection to a matching row. `n` and `N` continue match navigation.
The initial mode is normal navigation, not text input.

The bottom line is used only for transient state: search input, command input,
numeric count, or status messages. Full key hints are available from `:help`.
When no transient state is visible, separators and content should fill the rows
that a footer would otherwise occupy.
The popup shell should hide the terminal cursor before Python starts and restore
it on exit. Inside curses, normal/help/loading views keep the cursor hidden;
search and command modes show it for text editing.

When focus is on pinned phrases, the upper right pane previews the selected pin
instead of the currently selected tmux buffer. Pins should not show a `>` marker
while focus remains on the buffer list.

## Recommended Approach

Use a small Python standard-library curses program for the TUI, with the
existing shell script remaining the tmux command adapter.

This keeps runtime dependencies low while avoiding the complexity of writing a
terminal renderer, key reader, search field, resize handling, and preview layout
in POSIX shell. The plugin should still support `@better-copy-buffer-ui native`
as the no-Python fallback path.

## Architecture

The TPM entrypoint owns key bindings and popup dimensions. When
`@better-copy-buffer-ui` is `tui`, `prefix =` opens `tmux display-popup` through
a fast path: `run-shell -C` expands the invoking `#{pane_id}` into
`TMUX_BCB_TARGET`, then the popup shell starts `scripts/tui.py` directly.
`choose-tui` remains available as a compatibility command and fallback path, but
is not on the default startup path.

```text
python scripts/tui.py tmux-better-copy-buffer.sh "$TMUX_BCB_TARGET" <preview> <pins-db>
```

The shell script keeps the authoritative tmux operations:

- list supported buffers;
- preview a buffer;
- paste and refresh recency;
- delete a buffer;
- edit a buffer.

The Python TUI is responsible for:

- rendering the list, search prompt, footer, current buffer content, and pins;
- tracking buffer and pin focus, selections, scroll offsets, query, and right
  pane visibility;
- interpreting key presses;
- calling the shell command for tmux operations;
- reloading rows after paste-affecting, delete, or edit actions.
- creating and querying the SQLite pins database through Python's standard
  `sqlite3` module.
- drawing a lightweight loading screen before calling tmux to load rows, so
  tmux client cold starts do not block the first visible popup frame.

Suggested files:

- `scripts/tmux-better-copy-buffer.sh`: add `choose-tui`, `list-tui-rows`,
  `delete`, `edit`, and `paste-text-file` commands; keep existing paste and
  native chooser paths.
- `scripts/tui.py`: implement curses UI and subprocess calls into the shell
  command.
- `tmux-better-copy-buffer.tmux`: default `@better-copy-buffer-ui` to `tui` and
  bind popup execution to the direct Python TUI fast path.
- `run_tests`: add focused shell tests plus attached tmux popup smoke tests.
- `README.md` and `CONTEXT.md`: document the TUI, keymap, Python dependency
  expectation, and native fallback.

## Data Flow

The row list command should emit a stable, tab-separated format:

```text
<created>\t<buffer-name>\t<single-line-sample>
```

Rows are sorted newest first by `buffer_created`. The TUI stores the hidden
buffer name and displays only the sample. Samples normalize tabs and carriage
returns to spaces and use `<empty>` for empty samples.

Preview remains lazy. The TUI calls the preview command only for the selected
buffer when preview is visible:

```text
tmux-better-copy-buffer.sh preview <buffer-name>
```

Paste uses the existing recency path:

```text
tmux-better-copy-buffer.sh paste-touch <buffer-name> <target-pane>
```

Pins use a SQLite database at
`${XDG_DATA_HOME:-~/.local/share}/tmux-better-copy-buffer/pins.sqlite3` by
default, configurable via `@better-copy-buffer-pins-db`. The schema stores
unique text content plus creation, update, and last-used timestamps.

Pinned text is pasted through the shell adapter instead of direct tmux calls
from Python:

```text
tmux-better-copy-buffer.sh paste-text-file <file> <target-pane>
```

This command loads the file into a short-lived tmux buffer, pastes it into the
invoking pane, and deletes that temporary tmux buffer.

## Editing

`e` should edit the selected tmux buffer through a shell command rather than
inside curses itself. The edit command saves the buffer to a temporary file,
opens `${VISUAL:-${EDITOR:-vi}}`, then reloads the edited file back into the same
buffer name.

After the editor exits, the TUI reloads the row list and keeps the cursor near
the edited buffer when possible.

When focus is on pinned phrases, `e` edits the selected pin through
`${VISUAL:-${EDITOR:-vi}}`, updates the SQLite row, and keeps the edited pin
selected. `d` deletes the selected pin.

## Configuration

Primary UI values:

```tmux
set -g @better-copy-buffer-ui tui
set -g @better-copy-buffer-ui native
```

Popup size uses TUI-specific options:

```tmux
set -g @better-copy-buffer-popup-width 95%
set -g @better-copy-buffer-popup-height 90%
```

Preview starts visible by default:

```tmux
set -g @better-copy-buffer-tui-preview on
```

Pinned common phrases are stored in SQLite:

```tmux
set -g @better-copy-buffer-pins-db '~/.local/share/tmux-better-copy-buffer/pins.sqlite3'
```

The custom TUI is the default UI. The native tmux chooser remains available with
`@better-copy-buffer-ui native`.

## Error Handling

No supported buffers:

- close the popup;
- show `tmux-better-copy-buffer: no buffers` when display messages are enabled;
- do not paste.

Python or curses unavailable:

- fall back to the native chooser;
- show a short tmux message explaining the fallback when display messages are
  enabled.

Delete failure, edit failure, or preview failure:

- keep the TUI open;
- show a one-line status message in the footer;
- do not corrupt the selection state.

Unsupported buffer name:

- keep validation in shell commands as the final guard.

Pins database failure:

- keep the buffer list usable;
- show a one-line footer status;
- avoid pasting or modifying a pin when the SQLite operation fails.

Terminal too small:

- render a compact list-only layout;
- hide preview automatically if there is not enough space.

## Testing

Tests should cover:

- default binding opens the Python TUI fast path in a popup and passes the
  invoking pane through `TMUX_BCB_TARGET`;
- `@better-copy-buffer-ui native` still binds native `choose-buffer`;
- newest-first row sorting;
- row formatting hides internal buffer names from display data used by the TUI;
- `Enter` pastes into the invoking pane and refreshes recency;
- `d` deletes the selected buffer and refreshes rows;
- `e` round-trips a buffer through a fake editor;
- `q` exits without paste;
- preview command remains lazy and rejects unsupported names;
- `p` persists a selected buffer as one unique SQLite pin;
- `Tab` moves focus to pins;
- `Enter` in pin focus pastes through `paste-text-file`;
- `d` and `e` manage pins;
- missing Python/curses falls back to native chooser;
- shell syntax checks and Python syntax checks pass.

Attached tmux smoke tests should verify at least `Enter`, `d`, and `q` through
the popup because those are the highest-risk integration points.

## Out of Scope

- A standalone clipboard history database.
- Cross-application clipboard history.
- Mouse controls.
- Multi-select actions.
- Full fuzzy ranking parity with dedicated fuzzy finder tools.
- Rich syntax highlighting inside previews.
