# Release process

This plugin is installed by TPM directly from Git. There is no build artifact to
publish.

## Before tagging

1. Run the local test suite:

   ```sh
   ./run_tests
   ./tests/tpm_install_e2e "$PWD"
   ```

2. Check that the public install smoke test works after pushing to `main`:

   ```sh
   ./tests/tpm_install_e2e NaroZeol/tmux-better-copy-buffer
   ```

3. Confirm the README install snippet still matches the public repository:

   ```tmux
   set -g @plugin 'NaroZeol/tmux-better-copy-buffer'
   ```

## Tagging

Use semantic version tags:

```sh
git tag -a v0.1.0 -m "v0.1.0"
git push origin v0.1.0
```

Pushing a `v*` tag triggers the release workflow. The workflow reruns the tmux
E2E tests, verifies TPM can install the tagged plugin with
`NaroZeol/tmux-better-copy-buffer#<tag>`, and creates a GitHub Release with
generated notes.

## User-facing install paths

Most users should track the default branch:

```tmux
set -g @plugin 'NaroZeol/tmux-better-copy-buffer'
```

Users who want a fixed version can pin a tag:

```tmux
set -g @plugin 'NaroZeol/tmux-better-copy-buffer#v0.1.0'
```
