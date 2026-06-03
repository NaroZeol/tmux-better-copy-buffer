# tmux-better-copy-buffer Context

## Domain Terms

### Paste Buffer

A tmux paste buffer containing copied text. The MVP supports tmux auto-style buffer names only: `buffer` followed by digits.

### Native Buffer Chooser

tmux's built-in `choose-buffer` mode. The plugin keeps this UI as the default chooser experience.

### Last-Used Ordering

The user-facing ordering where the most recently pasted buffer appears first. The MVP approximates this by refreshing tmux's `buffer_created` timestamp after paste.

### Paste and Refresh

The transaction that saves a supported paste buffer, pastes it, and reloads it under the same name so tmux treats it as recent.

### Recency Strategy

The way a pasted buffer becomes latest. `touch` preserves the buffer name and refreshes the timestamp. `recreate` deletes the used buffer after paste and reloads it without a name so tmux assigns a new auto buffer name.

### tmux Adapter

The Module that owns how this project calls tmux: socket selection, option lookup, display messages, and command execution conventions. Runtime code and tests should cross this seam instead of spelling out tmux command details repeatedly.
