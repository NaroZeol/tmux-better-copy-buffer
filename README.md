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
tmux source-file /path/to/tmux-better-copy-buffer/tmux-better-copy-buffer.tmux
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

# How a pasted buffer becomes latest. Default: touch
# touch: keep the same buffer name and refresh its timestamp.
# recreate: delete the old buffer and let tmux create a new auto name.
set -g @better-copy-buffer-recency-strategy touch
```

Disable automatic bindings if you want to wire commands yourself:

```tmux
set -g @better-copy-buffer-bind-keys off
```

## Project structure

- `tmux-better-copy-buffer.tmux` is the TPM entrypoint.
- `scripts/tmux-better-copy-buffer.sh` is the command runner for chooser and paste actions.
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
`tmux`, and `script`.

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
