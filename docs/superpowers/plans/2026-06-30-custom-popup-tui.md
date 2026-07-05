# Custom Popup TUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the default external-selector popup with a plugin-owned Python curses popup TUI for tmux paste buffers.

**Architecture:** Keep tmux as the source of truth and keep shell commands as the tmux adapter. Add a focused Python curses renderer that calls the shell adapter for list, preview, paste, delete, and edit operations. Keep tmux native `choose-buffer` as the fallback and opt-out path.

**Tech Stack:** POSIX shell, tmux commands, Python 3 standard-library curses, existing shell/tmux E2E harness.

---

## File Structure

- Modify `tmux-better-copy-buffer.tmux`: default to `@better-copy-buffer-ui tui`, bind popup to `choose-tui`, and use `@better-copy-buffer-popup-width` / `@better-copy-buffer-popup-height`.
- Modify `scripts/tmux-better-copy-buffer.sh`: add `choose-tui`, `list-tui-rows`, `delete`, and `edit`; remove the external selector dependency path.
- Create `scripts/tui.py`: render and handle the custom TUI.
- Modify `run_tests`: replace old selector tests with TUI row, command, fake program, and attached popup tests.
- Modify `tests/tpm_install_e2e`: assert default TPM binding runs `choose-tui`.
- Modify `README.md` and `CONTEXT.md`: document the custom TUI, keymap, Python expectation, and native fallback.

## Task 1: Shell Adapter Tests

- [ ] Rewrite binding tests to expect `display-popup ... choose-tui '#{pane_id}'`.
- [ ] Rewrite row tests to call `list-tui-rows` and assert newest-first rows include `<created>\t<buffer>\t<sample>`.
- [ ] Add direct tests for `delete <buffer>` and `edit <buffer>`.
- [ ] Add a fake TUI executable test proving `choose-tui` passes script path, target pane, and preview default.
- [ ] Add a missing Python test proving `choose-tui` falls back to native `choose-buffer`.

## Task 2: Shell Adapter Implementation

- [ ] Add `list_tui_rows` and sample normalization with newest-first sorting.
- [ ] Add `delete_buffer` with auto-buffer validation.
- [ ] Add `edit_buffer` using a temporary file and `${VISUAL:-${EDITOR:-vi}}`.
- [ ] Add Python discovery and `choose_tui`.
- [ ] Remove runtime dependency hint commands for the old selector path.

## Task 3: Python TUI

- [ ] Create `scripts/tui.py`.
- [ ] Implement row loading and parsing through `list-tui-rows`.
- [ ] Implement normal mode keys: `j`, `k`, `Enter`, `d`, `e`, `v`, `q`, `/`.
- [ ] Implement search mode: printable input filters rows, `Esc` returns to normal, `Enter` pastes.
- [ ] Implement lazy preview loading and `v` preview toggle.
- [ ] Keep rendering compact: prompt, single-column sample list, optional preview pane, and footer.

## Task 4: Popup E2E

- [ ] Add attached tmux popup smoke for `Enter` paste.
- [ ] Add attached tmux popup smoke for `d` delete.
- [ ] Add attached tmux popup smoke for `q` cancel.
- [ ] Keep native chooser E2E coverage.

## Task 5: Docs and Verification

- [ ] Update README configuration and feature docs for the custom TUI.
- [ ] Update context docs.
- [ ] Update TPM E2E expectations.
- [ ] Run shell syntax checks, Python syntax checks, `git diff --check`, and `./run_tests`.
