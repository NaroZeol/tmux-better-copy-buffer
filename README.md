# tmux-better-copy-buffer

A small TPM-compatible tmux plugin that makes copy buffers behave closer to "last used first".

## What it does

- `prefix =` opens a custom popup TUI; if Python curses is unavailable, it falls back to tmux's native `choose-buffer`.
- Choosing a supported buffer through the enhanced command pastes it and refreshes its tmux buffer timestamp.
- `prefix ]` pastes the current latest buffer through the same refresh path, so `]` and `=` agree on what "latest" means.
- The TUI shows buffer samples, searches them with Vim-style `/`, lazily previews the focused buffer or pinned phrase, and pastes through the same recency refresh path.
- The TUI fills the selected row across the pane using the tmux status-line background color, pure black/white contrast text, and bold text.
- The TUI uses tmux-style box drawing separators in white.
- The TUI can pin a selected buffer as a persistent common phrase, stored in SQLite and shown in the lower half of the right pane.
- The TUI keeps the bottom area clear during normal navigation; `:help` opens the full key reference.
- In the TUI, `j`/`k`, numeric prefixes, `gg`/`G`, `H`/`M`/`L`, `C-d`/`C-u`, `C-f`/`C-b`, and PageUp/PageDown navigate with Vim-style behavior.
- `/` starts search, `n`/`N` jump between matches, `Enter` pastes, `p` pins, `Tab` switches to common phrases, `d` deletes, `e` edits, `v` cycles the persisted preview/pins layout, `:help` shows keys, and `q`/plain `Esc`/`C-c` quits.
- The native chooser remains available as a fallback or explicit configuration option.

The implementation uses tmux's own paste buffer commands. The default popup UI uses Python standard-library modules including `curses` and `sqlite3`; it does not require Node or Ruby.
The popup draws a lightweight first screen before loading tmux rows, so tmux buffer enumeration does not block initial visual feedback.
The popup shell hides the terminal cursor before Python starts and restores it on exit; search and command prompts still show the cursor while editing.

## Installation with TPM

Add the plugin to `.tmux.conf`:

```tmux
set -g @plugin 'NaroZeol/tmux-better-copy-buffer'
```

Then install with TPM:

```text
prefix + I
```

Make sure TPM itself is loaded at the end of `.tmux.conf`:

```tmux
run '~/.tmux/plugins/tpm/tpm'
```

Users who want to pin a release can install a tagged version:

```tmux
set -g @plugin 'NaroZeol/tmux-better-copy-buffer#v0.1.0'
```

For local development, clone this repository and execute the entrypoint from tmux:

```sh
/path/to/tmux-better-copy-buffer/tmux-better-copy-buffer.tmux
```

## Configuration

```tmux
# Bind the plugin keys. Default: on
set -g @better-copy-buffer-bind-keys on

# Chooser key. Default: =
set -g @better-copy-buffer-choose-key =

# Paste latest key. Default: ]
set -g @better-copy-buffer-paste-key ]

# Chooser UI. Default: tui
# tui falls back to native if Python curses is unavailable.
# Use native to opt out of the popup UI.
set -g @better-copy-buffer-ui tui
# set -g @better-copy-buffer-ui native

# TUI popup dimensions. Defaults: 95% x 90%
set -g @better-copy-buffer-popup-width 95%
set -g @better-copy-buffer-popup-height 90%

# TUI layout. Default: both
# v cycles: both -> preview -> pins -> none -> both.
set -g @better-copy-buffer-tui-layout both

# Legacy initial preview option used only when @better-copy-buffer-tui-layout is unset.
set -g @better-copy-buffer-tui-preview on

# SQLite file for pinned common phrases.
# Default: ${XDG_DATA_HOME:-~/.local/share}/tmux-better-copy-buffer/pins.sqlite3
set -g @better-copy-buffer-pins-db '~/.local/share/tmux-better-copy-buffer/pins.sqlite3'

# Reverse native chooser time sort. Default: off
set -g @better-copy-buffer-reverse-sort off

# Start the native chooser with preview visible. Default: on
# Set to off to reduce open latency when buffers are large.
set -g @better-copy-buffer-preview on

# Open the native chooser in a zoomed pane. Default: off
set -g @better-copy-buffer-zoom off

# Native chooser row format. Default: #{buffer_sample}
# For very large buffer lists, this is fastest:
# set -g @better-copy-buffer-list-format '#{buffer_name} #{buffer_size} bytes'
set -g @better-copy-buffer-list-format '#{buffer_sample}'

# Show plugin status messages on failures. Default: on
set -g @better-copy-buffer-display-messages on

# How a pasted buffer becomes latest. Default: touch
# touch: keep the same buffer name and refresh its timestamp.
# recreate: delete the old buffer and let tmux create a new auto name.
set -g @better-copy-buffer-recency-strategy touch
```

Disable automatic bindings if you want to wire commands yourself:

```tmux
set -g @better-copy-buffer-bind-keys off
```

## Python curses dependency

The popup UI uses Python's standard-library `curses` module. Most macOS and Linux developer environments already provide it through `python3`.

If Python or curses is unavailable, `prefix =` falls back to tmux's native chooser and shows a short status message. You can also opt out explicitly:

```tmux
set -g @better-copy-buffer-ui native
```

Set `TMUX_BCB_PYTHON` if you want the plugin to use a specific Python executable for the TUI.

## Project structure

- `tmux-better-copy-buffer.tmux` is the TPM entrypoint.
- `scripts/tmux-better-copy-buffer.sh` is the command runner for chooser, fallback, and paste actions.
- `scripts/tui.py` is the custom popup TUI.
- `scripts/lib/tmux.sh` is the tmux adapter used by runtime code and tests.
- `run_tests` is the shell E2E harness.
- `tests/tpm_install_e2e` verifies the plugin through TPM's install path.
- `.github/workflows/e2e.yml` runs syntax checks, isolated tmux tests, and TPM install E2E.
- `.github/workflows/release.yml` validates `v*` tags and creates GitHub Releases.
- `docs/RELEASE.md` documents the maintainer release process.
- `CONTEXT.md` records the project vocabulary for future agents and contributors.

## Limitations

- MVP supports tmux auto-style buffer names only: `buffer` followed by digits, such as `buffer0001`.
- Explicitly named buffers with arbitrary names are rejected by the plugin command.
- With the default `touch` strategy, last-used ordering is implemented by refreshing tmux's `buffer_created` timestamp after paste.
- Because of that, tmux's `buffer-limit` eviction order also treats recently used buffers as newer.
- With `@better-copy-buffer-recency-strategy recreate`, the used buffer gets a new tmux auto name and the old name disappears.
- The behavior has been tested locally with tmux 3.4.

## Tests

Run:

```sh
./run_tests
./tests/tpm_install_e2e "$PWD"
```

The tests are shell-based and start isolated tmux servers. They require `git`,
`tmux`, `script`, and Python with curses support for the popup TUI smoke tests.

The TPM install E2E can also verify the public repository:

```sh
./tests/tpm_install_e2e NaroZeol/tmux-better-copy-buffer
```

## CI and releases

Pushes and pull requests run GitHub Actions E2E against tmux and TPM. Pushes to
`main` also smoke-test installation from the public GitHub repository.

Version tags matching `v*` trigger a release workflow that validates the tagged
plugin through TPM and creates a GitHub Release. See `docs/RELEASE.md`.

## License

MIT
