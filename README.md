# tmux-better-copy-buffer

A small TPM-compatible tmux plugin that keeps tmux's native buffer UI while making copy buffers behave closer to "last used first".

## What it does

- `prefix =` opens tmux's native `choose-buffer` sorted by time.
- Choosing a supported buffer through the enhanced command pastes it and refreshes its tmux buffer timestamp.
- `prefix ]` pastes the current latest buffer through the same refresh path, so `]` and `=` agree on what "latest" means.
- The native chooser UI remains intact: preview, search, delete, edit, tagging, and sorting are still tmux features.

The implementation uses tmux's own paste buffer commands. It does not require `fzf`, Python, Node, Ruby, or a custom UI.

## Installation with TPM

Add the plugin to `.tmux.conf`:

```tmux
set -g @plugin 'NaroZeol/tmux-better-copy-buffer'
```

Then install with TPM:

```text
prefix + I
```

For local development, clone this repository and execute the entrypoint from tmux:

```sh
/path/to/tmux-better-copy-buffer/tmux-better-copy-buffer.tmux
```

## Configuration

```tmux
# Bind the plugin keys. Default: on
set -g @better-copy-buffer-bind-keys on

# Native chooser key. Default: =
set -g @better-copy-buffer-choose-key =

# Paste latest key. Default: ]
set -g @better-copy-buffer-paste-key ]

# Reverse native chooser time sort. Default: off
set -g @better-copy-buffer-reverse-sort off

# Show plugin status messages on failures. Default: on
set -g @better-copy-buffer-display-messages on
```

Disable automatic bindings if you want to wire commands yourself:

```tmux
set -g @better-copy-buffer-bind-keys off
```

## Limitations

- MVP supports tmux auto-style buffer names only: `buffer` followed by digits, such as `buffer0001`.
- Explicitly named buffers with arbitrary names are rejected by the plugin command.
- With the default `touch` strategy, last-used ordering is implemented by refreshing tmux's `buffer_created` timestamp after paste.
- Because of that, tmux's `buffer-limit` eviction order also treats recently used buffers as newer.
- The behavior has been tested locally with tmux 3.4.

## Tests

Run:

```sh
./run_tests
```

The tests are shell-based and start isolated tmux servers. They require `tmux` and `script`.
