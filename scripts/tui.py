#!/usr/bin/env python3
import curses
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unicodedata


ENTER_KEYS = {10, 13, curses.KEY_ENTER}
BACKSPACE_KEYS = {8, 127, curses.KEY_BACKSPACE}
ESC_DELAY_MS = 25
OPTION_COLOR_PAIR = 1
DIVIDER_COLOR_PAIR = 2
LAYOUTS = ("both", "preview", "pins", "none")
ANSI_BLACK = 0
ANSI_WHITE = 7
XTERM_BLACK = 16
XTERM_WHITE = 231
VLINE = "│"
HLINE = "─"
TEE_RIGHT = "├"
BASIC_TMUX_COLORS = {
    "black": 0,
    "red": 1,
    "green": 2,
    "yellow": 3,
    "blue": 4,
    "magenta": 5,
    "cyan": 6,
    "white": 7,
    "brightblack": 8,
    "grey": 8,
    "gray": 8,
    "brightred": 9,
    "brightgreen": 10,
    "brightyellow": 11,
    "brightblue": 12,
    "brightmagenta": 13,
    "brightcyan": 14,
    "brightwhite": 15,
}


class Row:
    def __init__(self, created, name, sample):
        self.created = created
        self.name = name
        self.sample = sample


class Pin:
    def __init__(self, pin_id, content, created_at, updated_at, used_at):
        self.pin_id = pin_id
        self.content = content
        self.created_at = created_at
        self.updated_at = updated_at
        self.used_at = used_at

    @property
    def sample(self):
        return content_sample(self.content)


def run_script(script_path, args, capture=True):
    if capture:
        return subprocess.run(
            [script_path] + args,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ.copy(),
        )
    return subprocess.run([script_path] + args, env=os.environ.copy())


def configure_escape_delay():
    os.environ["ESCDELAY"] = str(ESC_DELAY_MS)
    set_escdelay = getattr(curses, "set_escdelay", None)
    if set_escdelay is None:
        return
    try:
        set_escdelay(ESC_DELAY_MS)
    except curses.error:
        pass


def layout_from_preview_default(preview_default):
    return "both" if preview_default == "on" else "none"


def normalize_layout(value, preview_default="on"):
    if value in LAYOUTS:
        return value
    return layout_from_preview_default(preview_default)


def layout_label(value):
    labels = {
        "both": "preview + pins",
        "preview": "preview",
        "pins": "pins",
        "none": "hidden",
    }
    return labels.get(value, "preview + pins")


def clean_text(value):
    return value.replace("\t", "    ").replace("\r", " ")


def content_sample(value):
    for line in value.splitlines():
        line = clean_text(line)
        if line:
            return line
    return "<empty>"


def cell_width(value):
    total = 0
    for char in value:
        total += char_cell_width(char)
    return total


def char_cell_width(char):
    if unicodedata.combining(char):
        return 0
    if unicodedata.east_asian_width(char) in ("F", "W"):
        return 2
    return 1


def clipped(value, width):
    if width <= 0:
        return ""
    value = clean_text(value)
    if cell_width(value) <= width:
        return value
    if width == 1:
        return "~"

    limit = width - 1
    used = 0
    output = []
    for char in value:
        char_width = char_cell_width(char)
        if used + char_width > limit:
            break
        output.append(char)
        used += char_width
    return "".join(output) + "~"


def padded(value, width):
    value = clipped(value, width)
    return value + (" " * max(0, width - cell_width(value)))


def add_text(stdscr, y, x, value, width, attr=0):
    if y < 0 or x < 0 or width <= 0:
        return
    try:
        stdscr.addstr(y, x, clipped(value, width), attr)
    except curses.error:
        pass


def add_filled_text(stdscr, y, x, value, width, attr=0):
    if y < 0 or x < 0 or width <= 0:
        return
    try:
        stdscr.addstr(y, x, padded(value, width), attr)
    except curses.error:
        pass


def file_ends_with_newline(path):
    try:
        size = os.path.getsize(path)
        if size <= 0:
            return False
        with open(path, "rb") as handle:
            handle.seek(-1, os.SEEK_END)
            return handle.read(1) == b"\n"
    except OSError:
        return False


def strip_final_newline_if_original_lacked_one(path, original_content):
    if original_content.endswith("\n") or not file_ends_with_newline(path):
        return
    size = os.path.getsize(path)
    with open(path, "r+b") as handle:
        handle.truncate(max(0, size - 1))


def status_bg_from_style(style):
    for part in style.replace(",", " ").split():
        key, separator, value = part.partition("=")
        if separator and key.strip().lower() == "bg":
            return value.strip()
    return ""


def xterm_palette():
    palette = [
        (0, 0, 0),
        (128, 0, 0),
        (0, 128, 0),
        (128, 128, 0),
        (0, 0, 128),
        (128, 0, 128),
        (0, 128, 128),
        (192, 192, 192),
        (128, 128, 128),
        (255, 0, 0),
        (0, 255, 0),
        (255, 255, 0),
        (0, 0, 255),
        (255, 0, 255),
        (0, 255, 255),
        (255, 255, 255),
    ]
    levels = [0, 95, 135, 175, 215, 255]
    for red in levels:
        for green in levels:
            for blue in levels:
                palette.append((red, green, blue))
    for index in range(24):
        value = 8 + index * 10
        palette.append((value, value, value))
    return palette


def tmux_color_to_rgb(value):
    value = value.strip().lower()
    if not value or value == "default":
        return None
    if len(value) == 7 and value.startswith("#"):
        try:
            return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))
        except ValueError:
            return None

    color = tmux_color_to_curses_color(value)
    palette = xterm_palette()
    if color is not None and 0 <= color < len(palette):
        return palette[color]
    return None


def nearest_xterm_color(red, green, blue):
    best_index = 0
    best_distance = None
    for index, (candidate_red, candidate_green, candidate_blue) in enumerate(xterm_palette()):
        distance = (
            (red - candidate_red) ** 2
            + (green - candidate_green) ** 2
            + (blue - candidate_blue) ** 2
        )
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_index = index
    return best_index


def relative_luminance(red, green, blue):
    def linear(channel):
        value = channel / 255
        if value <= 0.03928:
            return value / 12.92
        return ((value + 0.055) / 1.055) ** 2.4

    return 0.2126 * linear(red) + 0.7152 * linear(green) + 0.0722 * linear(blue)


def contrast_foreground_for_background(value, colors=0):
    rgb = tmux_color_to_rgb(value)
    if rgb is None:
        return -1
    if relative_luminance(*rgb) >= 0.179:
        return XTERM_BLACK if colors >= 256 else ANSI_BLACK
    return XTERM_WHITE if colors >= 256 else ANSI_WHITE


def tmux_color_to_curses_color(value):
    value = value.strip().lower()
    if not value or value == "default":
        return None
    if value in BASIC_TMUX_COLORS:
        return BASIC_TMUX_COLORS[value]
    if value.startswith("colour") or value.startswith("color"):
        digits = value[6:] if value.startswith("colour") else value[5:]
        if digits.isdigit():
            return int(digits)
    if len(value) == 7 and value.startswith("#"):
        try:
            red = int(value[1:3], 16)
            green = int(value[3:5], 16)
            blue = int(value[5:7], 16)
        except ValueError:
            return None
        return nearest_xterm_color(red, green, blue)
    return None


class App:
    def __init__(self, stdscr, script_path, target_pane, preview_default, pins_db_path="", layout_default=""):
        self.stdscr = stdscr
        self.script_path = script_path
        self.target_pane = target_pane
        self.preview_visible = preview_default == "on"
        self.layout = normalize_layout(layout_default, preview_default)
        self.pins_db_path = pins_db_path
        self.mode = "normal"
        self.focus = "buffers"
        self.query = ""
        self.command_query = ""
        self.search_pattern = ""
        self.pending_count = ""
        self.pending_g = False
        self.rows = []
        self.selected = 0
        self.scroll = 0
        self.pins = []
        self.selected_pin = 0
        self.pin_scroll = 0
        self.list_page_size = 1
        self.pin_page_size = 1
        self.status = ""
        self.status_until = 0
        self.preview_cache = {}
        self.loading = False
        self.status_style = os.environ.get("TMUX_BCB_STATUS_STYLE", "")
        self.option_attr = 0
        self.divider_attr = 0
        self.undo_stack = []
        self.redo_stack = []

    def init_option_style(self):
        self.option_attr = 0
        bg_value = status_bg_from_style(self.status_style)
        color = tmux_color_to_curses_color(bg_value)
        if color is None:
            return
        try:
            colors = getattr(curses, "COLORS", 0)
            foreground = contrast_foreground_for_background(bg_value, colors)
            if not curses.has_colors() or color >= colors or foreground >= colors:
                return
            curses.init_pair(OPTION_COLOR_PAIR, foreground, color)
            self.option_attr = curses.color_pair(OPTION_COLOR_PAIR)
        except curses.error:
            self.option_attr = 0

    def init_divider_style(self):
        self.divider_attr = 0
        try:
            colors = getattr(curses, "COLORS", 0)
            foreground = XTERM_WHITE if colors >= 256 else ANSI_WHITE
            if not curses.has_colors() or foreground >= colors:
                return
            curses.init_pair(DIVIDER_COLOR_PAIR, foreground, -1)
            self.divider_attr = curses.color_pair(DIVIDER_COLOR_PAIR)
        except curses.error:
            self.divider_attr = 0

    def set_status(self, value, seconds=3):
        self.status = value
        self.status_until = time.time() + seconds

    def visible_status(self):
        if self.status and time.time() < self.status_until:
            return self.status
        return ""

    def pins_db(self):
        if not self.pins_db_path:
            return None
        path = os.path.expanduser(self.pins_db_path)
        if path != ":memory:":
            directory = os.path.dirname(os.path.abspath(path))
            if directory:
                os.makedirs(directory, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pins (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              content TEXT NOT NULL UNIQUE,
              created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL,
              used_at INTEGER
            )
            """
        )
        return conn

    def load_pins(self):
        if not self.pins_db_path:
            self.pins = []
            self.selected_pin = 0
            self.pin_scroll = 0
            return
        try:
            with self.pins_db() as conn:
                rows = conn.execute(
                    """
                    SELECT id, content, created_at, updated_at, used_at
                    FROM pins
                    ORDER BY COALESCE(used_at, 0) DESC, updated_at DESC, id DESC
                    """
                ).fetchall()
        except (OSError, sqlite3.Error) as exc:
            self.pins = []
            self.selected_pin = 0
            self.pin_scroll = 0
            self.set_status(f"pins unavailable: {exc}")
            return
        self.pins = [Pin(*row) for row in rows]
        self.clamp_pin_selection()

    def load_rows(self):
        result = run_script(self.script_path, ["list-tui-rows"])
        if result.returncode != 0:
            message = result.stderr.strip() or "failed to load buffers"
            self.rows = []
            self.set_status(message)
            return

        rows = []
        for line in result.stdout.splitlines():
            parts = line.split("\t", 2)
            if len(parts) != 3:
                continue
            rows.append(Row(parts[0], parts[1], parts[2]))
        self.rows = rows
        self.clamp_selection()

    def filtered_rows(self):
        return self.rows

    def selected_row(self):
        rows = self.filtered_rows()
        if not rows:
            return None
        if self.selected >= len(rows):
            self.selected = len(rows) - 1
        if self.selected < 0:
            self.selected = 0
        return rows[self.selected]

    def clamp_selection(self):
        rows = self.filtered_rows()
        if not rows:
            self.selected = 0
            self.scroll = 0
            return
        if self.selected >= len(rows):
            self.selected = len(rows) - 1
        if self.selected < 0:
            self.selected = 0

    def clamp_pin_selection(self):
        if not self.pins:
            self.selected_pin = 0
            self.pin_scroll = 0
            return
        if self.selected_pin >= len(self.pins):
            self.selected_pin = len(self.pins) - 1
        if self.selected_pin < 0:
            self.selected_pin = 0

    def ensure_visible(self, height):
        if height <= 0:
            self.scroll = 0
            return
        if self.selected < self.scroll:
            self.scroll = self.selected
        if self.selected >= self.scroll + height:
            self.scroll = self.selected - height + 1
        if self.scroll < 0:
            self.scroll = 0

    def ensure_pin_visible(self, height):
        if height <= 0:
            self.pin_scroll = 0
            return
        if self.selected_pin < self.pin_scroll:
            self.pin_scroll = self.selected_pin
        if self.selected_pin >= self.pin_scroll + height:
            self.pin_scroll = self.selected_pin - height + 1
        if self.pin_scroll < 0:
            self.pin_scroll = 0

    def move(self, delta):
        rows = self.filtered_rows()
        if not rows:
            return
        self.selected = max(0, min(len(rows) - 1, self.selected + delta))
        self.status = ""

    def move_pin(self, delta):
        if not self.pins:
            return
        self.selected_pin = max(0, min(len(self.pins) - 1, self.selected_pin + delta))
        self.status = ""

    def move_active(self, delta):
        if self.focus == "pins":
            self.move_pin(delta)
        else:
            self.move(delta)

    def active_length(self):
        if self.focus == "pins":
            return len(self.pins)
        return len(self.filtered_rows())

    def active_page_size(self):
        if self.focus == "pins":
            return max(1, self.pin_page_size)
        return max(1, self.list_page_size)

    def active_scroll(self):
        if self.focus == "pins":
            return self.pin_scroll
        return self.scroll

    def move_active_to(self, index):
        count = self.active_length()
        if count <= 0:
            return
        index = max(0, min(count - 1, index))
        if self.focus == "pins":
            self.selected_pin = index
        else:
            self.selected = index
        self.status = ""

    def move_active_to_visible_position(self, offset):
        self.move_active_to(self.active_scroll() + offset)

    def layout_shows_preview(self):
        return self.layout in ("both", "preview")

    def layout_shows_pins(self):
        return self.layout in ("both", "pins")

    def persist_layout(self):
        result = run_script(self.script_path, ["set-tui-layout", self.layout])
        if result.returncode == 0:
            self.set_status(f"layout: {layout_label(self.layout)}")
        else:
            self.set_status(f"layout: {layout_label(self.layout)} (not saved)")

    def cycle_layout(self):
        try:
            index = LAYOUTS.index(self.layout)
        except ValueError:
            index = 0
        self.layout = LAYOUTS[(index + 1) % len(LAYOUTS)]
        self.preview_visible = self.layout_shows_preview()
        if not self.layout_shows_pins() and self.focus == "pins":
            self.focus = "buffers"
        self.persist_layout()

    def consume_count(self):
        if not self.pending_count:
            return 1
        count = int(self.pending_count)
        self.pending_count = ""
        return max(1, count)

    def clear_count(self):
        self.pending_count = ""

    def row_matches_search(self, row):
        if not self.search_pattern:
            return False
        return self.search_pattern.lower() in row.sample.lower()

    def jump_to_search_match(self, direction):
        rows = self.filtered_rows()
        if not self.search_pattern:
            self.set_status("No search")
            return
        if not rows:
            self.set_status("Pattern not found")
            return

        count = len(rows)
        start = self.selected
        for step in range(1, count + 1):
            index = (start + direction * step) % count
            if self.row_matches_search(rows[index]):
                self.selected = index
                self.status = ""
                return
        self.set_status("Pattern not found")

    def commit_search(self):
        pattern = self.query
        self.mode = "normal"
        self.query = ""
        if not pattern:
            return
        self.search_pattern = pattern
        self.jump_to_search_match(1)

    def preview_text(self, row):
        if row is None:
            return ""
        if row.name in self.preview_cache:
            return self.preview_cache[row.name]
        result = run_script(self.script_path, ["preview", row.name])
        if result.returncode != 0:
            self.set_status("load failed")
            text = ""
        else:
            text = result.stdout.rstrip("\n")
        self.preview_cache[row.name] = text
        return text

    def selected_pin_obj(self):
        if not self.pins:
            return None
        if self.selected_pin >= len(self.pins):
            self.selected_pin = len(self.pins) - 1
        if self.selected_pin < 0:
            self.selected_pin = 0
        return self.pins[self.selected_pin]

    def select_pin_content(self, content):
        for index, pin in enumerate(self.pins):
            if pin.content == content:
                self.selected_pin = index
                return

    def select_buffer_name(self, name):
        for index, row in enumerate(self.filtered_rows()):
            if row.name == name:
                self.selected = index
                return

    def buffer_order_snapshot(self):
        return [row.name for row in self.filtered_rows()]

    def apply_buffer_order(self, names):
        if not names:
            return
        rows_by_name = {row.name: row for row in self.rows}
        ordered = []
        for name in names:
            row = rows_by_name.pop(name, None)
            if row is not None:
                ordered.append(row)
        ordered.extend(rows_by_name.values())
        self.rows = ordered
        self.clamp_selection()

    def select_pin_id(self, pin_id):
        for index, pin in enumerate(self.pins):
            if pin.pin_id == pin_id:
                self.selected_pin = index
                return

    def push_undo(self, change):
        self.undo_stack.append(change)
        self.redo_stack = []

    def pin_snapshot(self, pin):
        return {
            "id": pin.pin_id,
            "content": pin.content,
            "created_at": pin.created_at,
            "updated_at": pin.updated_at,
            "used_at": pin.used_at,
        }

    def write_buffer_content(self, name, content, order=None):
        fd, path = tempfile.mkstemp(prefix="tmux-bcb-undo-buffer.")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
            result = run_script(self.script_path, ["set-buffer-file", name, path])
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        if result.returncode != 0:
            self.set_status(result.stderr.strip() or "undo failed")
            return False
        self.preview_cache.pop(name, None)
        self.load_rows()
        self.apply_buffer_order(order)
        self.select_buffer_name(name)
        return True

    def delete_buffer_for_history(self, name, order=None):
        result = run_script(self.script_path, ["delete", name])
        if result.returncode != 0:
            self.set_status(result.stderr.strip() or "redo failed")
            return False
        self.preview_cache.pop(name, None)
        self.load_rows()
        self.apply_buffer_order(order)
        return True

    def restore_pin_snapshot(self, snapshot):
        if not self.pins_db_path:
            self.set_status("pins unavailable")
            return False
        try:
            with self.pins_db() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO pins(id, content, created_at, updated_at, used_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot["id"],
                        snapshot["content"],
                        snapshot["created_at"],
                        snapshot["updated_at"],
                        snapshot["used_at"],
                    ),
                )
        except (OSError, sqlite3.Error) as exc:
            self.set_status(f"undo failed: {exc}")
            return False
        self.load_pins()
        self.select_pin_id(snapshot["id"])
        return True

    def delete_pin_for_history(self, snapshot):
        if not self.pins_db_path:
            self.set_status("pins unavailable")
            return False
        try:
            with self.pins_db() as conn:
                conn.execute("DELETE FROM pins WHERE id = ?", (snapshot["id"],))
        except (OSError, sqlite3.Error) as exc:
            self.set_status(f"redo failed: {exc}")
            return False
        self.load_pins()
        return True

    def apply_history_change(self, change, direction):
        kind = change["kind"]
        if kind == "buffer-delete":
            if direction == "undo":
                return self.write_buffer_content(change["name"], change["content"], change.get("before_order"))
            return self.delete_buffer_for_history(change["name"], change.get("after_order"))
        if kind == "buffer-edit":
            content = change["before"] if direction == "undo" else change["after"]
            order = change.get("before_order") if direction == "undo" else change.get("after_order")
            return self.write_buffer_content(change["name"], content, order)
        if kind == "pin-add":
            if direction == "undo":
                return self.delete_pin_for_history(change["pin"])
            return self.restore_pin_snapshot(change["pin"])
        if kind == "pin-delete":
            if direction == "undo":
                return self.restore_pin_snapshot(change["pin"])
            return self.delete_pin_for_history(change["pin"])
        if kind == "pin-edit":
            snapshot = change["before"] if direction == "undo" else change["after"]
            return self.restore_pin_snapshot(snapshot)
        self.set_status("unknown undo item")
        return False

    def undo(self):
        if not self.undo_stack:
            self.set_status("Already at oldest change")
            return
        change = self.undo_stack.pop()
        if self.apply_history_change(change, "undo"):
            self.redo_stack.append(change)
            self.set_status("undone")
        else:
            self.undo_stack.append(change)

    def redo(self):
        if not self.redo_stack:
            self.set_status("Already at newest change")
            return
        change = self.redo_stack.pop()
        if self.apply_history_change(change, "redo"):
            self.undo_stack.append(change)
            self.set_status("redone")
        else:
            self.redo_stack.append(change)

    def pin_selected_buffer(self):
        row = self.selected_row()
        if row is None:
            self.set_status("no buffer selected")
            return
        if not self.pins_db_path:
            self.set_status("pins unavailable")
            return

        content = self.preview_text(row)
        now = int(time.time())
        try:
            with self.pins_db() as conn:
                conn.execute(
                    """
                    INSERT INTO pins(content, created_at, updated_at, used_at)
                    VALUES (?, ?, ?, NULL)
                    """,
                    (content, now, now),
                )
        except sqlite3.IntegrityError:
            self.load_pins()
            self.select_pin_content(content)
            self.set_status("already pinned")
            return
        except (OSError, sqlite3.Error) as exc:
            self.set_status(f"pin failed: {exc}")
            return

        self.load_pins()
        self.select_pin_content(content)
        pin = self.selected_pin_obj()
        if pin is not None:
            self.push_undo({"kind": "pin-add", "pin": self.pin_snapshot(pin)})
        self.set_status("pinned")

    def paste(self):
        row = self.selected_row()
        if row is None:
            self.set_status("no buffer selected")
            return False
        args = ["paste-touch", row.name]
        if self.target_pane:
            args.append(self.target_pane)
        result = run_script(self.script_path, args)
        if result.returncode == 0:
            return True
        self.set_status(result.stderr.strip() or "paste failed")
        return False

    def mark_pin_used(self, pin):
        try:
            with self.pins_db() as conn:
                conn.execute("UPDATE pins SET used_at = ? WHERE id = ?", (int(time.time()), pin.pin_id))
        except (OSError, sqlite3.Error):
            pass

    def paste_pin(self):
        pin = self.selected_pin_obj()
        if pin is None:
            self.set_status("no pin selected")
            return False

        fd, path = tempfile.mkstemp(prefix="tmux-bcb-pin.")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(pin.content)
            args = ["paste-text-file", path]
            if self.target_pane:
                args.append(self.target_pane)
            result = run_script(self.script_path, args)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

        if result.returncode == 0:
            self.mark_pin_used(pin)
            return True
        self.set_status(result.stderr.strip() or "paste failed")
        return False

    def delete_pin(self):
        pin = self.selected_pin_obj()
        if pin is None:
            self.set_status("no pin selected")
            return
        snapshot = self.pin_snapshot(pin)
        try:
            with self.pins_db() as conn:
                conn.execute("DELETE FROM pins WHERE id = ?", (pin.pin_id,))
        except (OSError, sqlite3.Error) as exc:
            self.set_status(f"delete failed: {exc}")
            return
        self.load_pins()
        self.push_undo({"kind": "pin-delete", "pin": snapshot})
        self.set_status("deleted")

    def run_editor(self, path):
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
        suspended = False
        try:
            curses.def_prog_mode()
            curses.endwin()
            suspended = True
        except curses.error:
            pass
        try:
            return subprocess.run(["sh", "-c", f'{editor} "$1"', "sh", path], env=os.environ.copy())
        finally:
            if suspended:
                try:
                    curses.reset_prog_mode()
                    self.stdscr.keypad(True)
                    curses.curs_set(0 if self.mode == "normal" else 1)
                except curses.error:
                    pass

    def edit_pin(self):
        pin = self.selected_pin_obj()
        if pin is None:
            self.set_status("no pin selected")
            return
        before = self.pin_snapshot(pin)

        fd, path = tempfile.mkstemp(prefix="tmux-bcb-pin-edit.")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(pin.content)
            result = self.run_editor(path)
            if result.returncode != 0:
                self.set_status("edit failed")
                return
            strip_final_newline_if_original_lacked_one(path, pin.content)
            with open(path, "r", encoding="utf-8") as handle:
                content = handle.read()
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

        try:
            with self.pins_db() as conn:
                conn.execute(
                    "UPDATE pins SET content = ?, updated_at = ? WHERE id = ?",
                    (content, int(time.time()), pin.pin_id),
                )
        except sqlite3.IntegrityError:
            self.set_status("duplicate pin")
            return
        except (OSError, sqlite3.Error) as exc:
            self.set_status(f"edit failed: {exc}")
            return

        self.load_pins()
        self.select_pin_content(content)
        after = self.selected_pin_obj()
        if after is not None and before["content"] != content:
            self.push_undo({"kind": "pin-edit", "before": before, "after": self.pin_snapshot(after)})
        self.set_status("edited")

    def delete(self):
        row = self.selected_row()
        if row is None:
            self.set_status("no buffer selected")
            return
        content = self.preview_text(row)
        before_order = self.buffer_order_snapshot()
        result = run_script(self.script_path, ["delete", row.name])
        if result.returncode == 0:
            self.preview_cache.pop(row.name, None)
            self.load_rows()
            self.push_undo(
                {
                    "kind": "buffer-delete",
                    "name": row.name,
                    "content": content,
                    "before_order": before_order,
                    "after_order": self.buffer_order_snapshot(),
                }
            )
            self.set_status("deleted")
            return
        self.set_status(result.stderr.strip() or "delete failed")

    def edit(self):
        row = self.selected_row()
        if row is None:
            self.set_status("no buffer selected")
            return
        before = self.preview_text(row)
        before_order = self.buffer_order_snapshot()
        curses.def_prog_mode()
        curses.endwin()
        try:
            result = run_script(self.script_path, ["edit", row.name], capture=False)
        finally:
            curses.reset_prog_mode()
            self.stdscr.keypad(True)
            try:
                curses.curs_set(0 if self.mode == "normal" else 1)
            except curses.error:
                pass
        if result.returncode == 0:
            self.preview_cache.pop(row.name, None)
            previous_name = row.name
            self.load_rows()
            for index, candidate in enumerate(self.filtered_rows()):
                if candidate.name == previous_name:
                    self.selected = index
                    break
            after = self.preview_text(row)
            if before != after:
                self.push_undo(
                    {
                        "kind": "buffer-edit",
                        "name": previous_name,
                        "before": before,
                        "after": after,
                        "before_order": before_order,
                        "after_order": self.buffer_order_snapshot(),
                    }
                )
            self.set_status("edited")
            return
        self.set_status("edit failed")

    def draw_pins(self, top, x, height, width):
        if height <= 0 or width <= 0:
            return
        self.ensure_pin_visible(height)
        if not self.pins:
            add_text(self.stdscr, top, x, "  <no pins>", width)
            return
        visible = self.pins[self.pin_scroll : self.pin_scroll + height]
        for offset, pin in enumerate(visible):
            index = self.pin_scroll + offset
            selected = self.focus == "pins" and index == self.selected_pin
            marker = "> " if selected else "  "
            attr = self.option_attr | curses.A_BOLD if selected else 0
            add_filled_text(self.stdscr, top + offset, x, marker + pin.sample, width, attr)

    def footer_lines(self):
        status = self.visible_status()
        if self.mode == "search":
            return ["/" + self.query]
        if self.mode == "command":
            return [":" + self.command_query]
        if self.pending_count:
            return [self.pending_count]
        if status:
            return [status]
        return []

    def draw_help(self, max_y, max_x):
        lines = [
            "Buffers",
            "  j/k move    [count]j/k jump    gg/G top/bottom    H/M/L screen rows",
            "  C-d/C-u half page              C-f/C-b page        PageUp/PageDown",
            "  Enter paste    / search    n/N next/prev    p pin    d/e change",
            "  u undo         C-r redo    v layout          Tab pins    q/Esc/C-c quit",
            "",
            "Pins",
            "  j/k move    [count]j/k jump    gg/G top/bottom    C-d/C-u half page",
            "  Enter paste    d delete    e edit    u undo    C-r redo    Tab buffers",
            "  q/Esc/C-c quit",
            "",
            "Commands: :help show this help   Esc leaves search/command/help first",
        ]
        for y, line in enumerate(lines[:max_y]):
            add_text(self.stdscr, y, 0, line, max_x)

    def draw(self):
        self.stdscr.erase()
        max_y, max_x = self.stdscr.getmaxyx()
        if max_y <= 0 or max_x <= 0:
            return

        if self.mode == "help":
            self.draw_help(max_y, max_x)
            try:
                curses.curs_set(0)
            except curses.error:
                pass
            self.stdscr.refresh()
            return

        footer_lines = self.footer_lines()
        footer_height = min(len(footer_lines), max_y)
        footer_top = max_y - footer_height
        body_top = 0
        body_bottom = max_y
        body_height = max(0, body_bottom - body_top)
        list_top = body_top
        list_height = body_height
        row = self.selected_row()
        show_preview = self.layout_shows_preview()
        show_pins = self.layout_shows_pins()
        right_pane_enabled = self.layout != "none" and max_y >= 8 and max_x >= 60 and (
            (show_preview and row is not None) or show_pins
        )

        if right_pane_enabled:
            preview_width = max(24, min(max_x // 2, 80))
            list_width = max(10, max_x - preview_width - 1)
            preview_x = list_width + 1
            preview_top = body_top
            preview_content_top = preview_top
            preview_height = body_height if show_preview else 0
            pins_divider_y = None
            pins_top = body_bottom
            pins_height = 0
            if show_preview and show_pins and body_height >= 6:
                preview_height = max(1, body_height // 2)
                pins_divider_y = body_top + preview_height
                pins_top = pins_divider_y + 1
                pins_height = max(0, body_bottom - pins_top)
            elif show_pins:
                pins_top = body_top
                pins_height = body_height
            for y in range(body_top, body_bottom):
                add_text(self.stdscr, y, list_width, VLINE, 1, self.divider_attr)
        else:
            list_width = max_x
            preview_width = 0
            preview_x = max_x
            preview_top = body_top
            preview_content_top = body_top
            preview_height = 0
            pins_divider_y = None
            pins_top = body_bottom
            pins_height = 0

        self.list_page_size = max(1, list_height)
        self.pin_page_size = max(1, pins_height)
        self.ensure_visible(list_height)
        rows = self.filtered_rows()
        if self.loading:
            add_text(self.stdscr, list_top, 0, "  <loading>", list_width)
        elif not rows:
            add_text(self.stdscr, list_top, 0, "  <no matches>", list_width)
        else:
            visible = rows[self.scroll : self.scroll + list_height]
            for offset, item in enumerate(visible):
                index = self.scroll + offset
                selected = self.focus == "buffers" and index == self.selected
                marker = "> " if index == self.selected else "  "
                attr = self.option_attr | curses.A_BOLD if selected else 0
                add_filled_text(self.stdscr, list_top + offset, 0, marker + item.sample, list_width, attr)

        preview = None
        if right_pane_enabled and show_preview and self.focus == "pins":
            pin = self.selected_pin_obj()
            if pin is not None:
                preview = pin.content
        elif right_pane_enabled and show_preview and row is not None:
            preview = self.preview_text(row)
        if preview is not None:
            lines = preview.splitlines() or ["<empty>"]
            for offset, line in enumerate(lines[:preview_height]):
                add_text(self.stdscr, preview_content_top + offset, preview_x, line, preview_width)
        if right_pane_enabled and show_pins and pins_height > 0:
            if pins_divider_y is not None:
                add_text(
                    self.stdscr,
                    pins_divider_y,
                    list_width,
                    TEE_RIGHT + (HLINE * preview_width),
                    preview_width + 1,
                    self.divider_attr,
                )
            self.draw_pins(pins_top, preview_x, pins_height, preview_width)

        for offset, footer in enumerate(footer_lines[:footer_height]):
            add_text(self.stdscr, footer_top + offset, 0, footer, max_x)

        if self.mode in ("search", "command"):
            try:
                curses.curs_set(1)
                self.stdscr.move(footer_top, min(max_x - 1, len(footer_lines[0])))
            except curses.error:
                pass
        else:
            try:
                curses.curs_set(0)
            except curses.error:
                pass

        self.stdscr.refresh()

    def handle_search_key(self, key):
        if key in ENTER_KEYS:
            self.commit_search()
            return None
        if key == 27:
            self.mode = "normal"
            self.query = ""
            return None
        if key in BACKSPACE_KEYS:
            self.query = self.query[:-1]
            self.selected = 0
            self.scroll = 0
            return None
        if 32 <= key <= 126:
            self.query += chr(key)
            self.selected = 0
            self.scroll = 0
        return None

    def handle_command_key(self, key):
        if key in ENTER_KEYS:
            command = self.command_query.strip()
            self.command_query = ""
            self.mode = "normal"
            if not command:
                return None
            if command in ("help", "h"):
                self.mode = "help"
                return None
            self.set_status(f"unknown command: {command}")
            return None
        if key == 27:
            self.mode = "normal"
            self.command_query = ""
            return None
        if key in BACKSPACE_KEYS:
            self.command_query = self.command_query[:-1]
            return None
        if 32 <= key <= 126:
            self.command_query += chr(key)
        return None

    def handle_help_key(self, key):
        if key in (27, ord("q"), ord("Q")):
            self.mode = "normal"
        return None

    def handle_normal_key(self, key):
        if self.pending_g:
            if key == 27:
                self.pending_g = False
                self.clear_count()
                return None
            self.pending_g = False
            if key == ord("g"):
                self.clear_count()
                self.move_active_to(0)
                return None
        if key == 27:
            if self.pending_count:
                self.clear_count()
                return None
            return "exit"
        if key == 3:
            self.clear_count()
            return "exit"
        if key == 18:
            count = self.consume_count()
            for _ in range(count):
                self.redo()
            return None
        if key == 9:
            self.clear_count()
            self.focus = "pins" if self.focus == "buffers" else "buffers"
            self.status = ""
            return None
        if ord("0") <= key <= ord("9"):
            if self.pending_count or key != ord("0"):
                self.pending_count += chr(key)
            return None
        if key == ord(":"):
            self.clear_count()
            self.mode = "command"
            self.command_query = ""
            self.status = ""
            return None
        if key in ENTER_KEYS:
            self.clear_count()
            if self.focus == "pins":
                return "exit" if self.paste_pin() else None
            return "exit" if self.paste() else None
        if key in (ord("q"), ord("Q")):
            self.clear_count()
            return "exit"
        if key == ord("g"):
            self.pending_g = True
            self.status = ""
            return None
        if key == ord("G"):
            self.clear_count()
            self.move_active_to(self.active_length() - 1)
            return None
        if key == ord("H"):
            self.clear_count()
            self.move_active_to_visible_position(0)
            return None
        if key == ord("M"):
            self.clear_count()
            self.move_active_to_visible_position(max(0, self.active_page_size() // 2))
            return None
        if key == ord("L"):
            self.clear_count()
            self.move_active_to_visible_position(self.active_page_size() - 1)
            return None
        if key in (4, 21):
            direction = 1 if key == 4 else -1
            amount = max(1, self.active_page_size() // 2) * self.consume_count()
            self.move_active(direction * amount)
            return None
        if key in (6, curses.KEY_NPAGE, 2, curses.KEY_PPAGE):
            direction = 1 if key in (6, curses.KEY_NPAGE) else -1
            amount = self.active_page_size() * self.consume_count()
            self.move_active(direction * amount)
            return None
        if key in (ord("j"), curses.KEY_DOWN):
            if self.focus == "pins":
                self.move_pin(self.consume_count())
            else:
                self.move(self.consume_count())
            return None
        if key in (ord("k"), curses.KEY_UP):
            if self.focus == "pins":
                self.move_pin(-self.consume_count())
            else:
                self.move(-self.consume_count())
            return None
        if key == ord("/"):
            self.clear_count()
            if self.focus == "pins":
                return None
            self.mode = "search"
            self.query = ""
            self.status = ""
            return None
        if key == ord("n"):
            self.clear_count()
            if self.focus == "pins":
                return None
            self.jump_to_search_match(1)
            return None
        if key == ord("N"):
            self.clear_count()
            if self.focus == "pins":
                return None
            self.jump_to_search_match(-1)
            return None
        if key == ord("p"):
            self.clear_count()
            if self.focus == "buffers":
                self.pin_selected_buffer()
            return None
        if key == ord("u"):
            count = self.consume_count()
            for _ in range(count):
                self.undo()
            return None
        if key in (ord("d"), ord("D")):
            self.clear_count()
            if self.focus == "pins":
                self.delete_pin()
            else:
                self.delete()
            return None
        if key in (ord("e"), ord("E")):
            self.clear_count()
            if self.focus == "pins":
                self.edit_pin()
            else:
                self.edit()
            return None
        if key in (ord("v"), ord("V")):
            self.clear_count()
            self.cycle_layout()
            return None
        return None

    def run(self):
        configure_escape_delay()
        curses.noecho()
        curses.cbreak()
        self.stdscr.keypad(True)
        try:
            curses.use_default_colors()
        except curses.error:
            pass
        self.init_option_style()
        self.init_divider_style()
        self.loading = True
        self.draw()
        self.load_rows()
        self.load_pins()
        self.loading = False

        while True:
            self.draw()
            key = self.stdscr.getch()
            if self.mode == "search":
                action = self.handle_search_key(key)
            elif self.mode == "command":
                action = self.handle_command_key(key)
            elif self.mode == "help":
                action = self.handle_help_key(key)
            else:
                action = self.handle_normal_key(key)
            if action == "exit":
                return 0


def curses_main(stdscr, script_path, target_pane, preview_default, pins_db_path, layout_default=""):
    return App(stdscr, script_path, target_pane, preview_default, pins_db_path, layout_default).run()


def main(argv):
    if len(argv) not in (5, 6):
        print("usage: tui.py <script-path> <target-pane> <preview-default> <pins-db> [layout]", file=sys.stderr)
        return 2
    os.environ["ESCDELAY"] = str(ESC_DELAY_MS)
    script_path, target_pane, preview_default, pins_db_path = argv[1], argv[2], argv[3], argv[4]
    layout_default = argv[5] if len(argv) == 6 else ""
    return curses.wrapper(curses_main, script_path, target_pane, preview_default, pins_db_path, layout_default)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
