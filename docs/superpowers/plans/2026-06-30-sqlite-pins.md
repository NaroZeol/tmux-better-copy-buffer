# SQLite Pins Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent pinned phrases to the custom TUI, stored in SQLite and managed from a lower preview-area pane.

**Architecture:** Keep tmux paste buffer operations in the shell adapter. Add SQLite pin storage and pin-focused UI behavior in `scripts/tui.py` using Python standard-library `sqlite3`; paste pinned text through a shell adapter command that loads a temporary file into tmux and pastes it into the invoking pane.

**Tech Stack:** POSIX shell, tmux commands, Python 3 standard library (`curses`, `sqlite3`), existing shell/tmux E2E harness.

---

## File Structure

- Modify `scripts/tmux-better-copy-buffer.sh`: pass the pins DB path to the TUI and add `paste-text-file <file> <target-pane>`.
- Modify `scripts/tui.py`: add SQLite pin storage, render pins in the lower right pane, and implement `p`, `Tab`, `Enter`, `d`, and `e` for pins.
- Modify `run_tests`: add Python unit-style TUI tests and shell adapter tests.
- Modify `tmux-better-copy-buffer.tmux`: pass configured `@better-copy-buffer-pins-db` through runtime options by relying on the shell script option lookup.
- Modify `README.md` and `docs/superpowers/specs/2026-06-30-custom-tui-design.md`: document pins DB and keymap.

## Tasks

- [x] Write failing shell tests for `paste-text-file` and pins DB option passing.
- [x] Write failing Python TUI tests for pin creation, duplicate prevention, focus switching, pin paste, delete, and edit.
- [x] Implement shell adapter support for pins DB path and file-based text paste.
- [x] Implement SQLite schema and pin storage helpers.
- [x] Implement TUI rendering for preview top half plus pins lower half.
- [x] Implement pin key handling.
- [x] Update docs.
- [x] Run full verification.
