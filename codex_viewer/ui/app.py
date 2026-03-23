import os
import re
import subprocess
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from codex_viewer.config import (
    APP_TITLE,
    MIN_WINDOW_SIZE,
    WINDOW_SIZE,
    get_active_palette,
    get_codex_sessions_dir,
    load_config,
    save_config,
)
from codex_viewer.parser import parse_codex_file, parse_date_from_relative_path
from codex_viewer.ui.settings_dialog import SettingsDialog


BRACKET_PATH_PATTERN = re.compile(r"\[([^\]]+)\]\s*\((.*?)\)", re.DOTALL)
INLINE_CODE_PATTERN = re.compile(r"`([^`]+)`")
ANGLE_TOKEN_PATTERN = re.compile(r"<[^>\r\n]+>")
ABORTED_BLOCK_PATTERN = re.compile(r"<turn_aborted>.*?</turn_aborted>", re.DOTALL | re.IGNORECASE)
WINDOWS_PATH_PATTERN = re.compile(r"[A-Za-z]:\\(?:[^\\\r\n]+\\)*[^\\\r\n]+")
ROLE_LABELS = {
    "user": "User",
    "assistant": "Assistant",
    "developer": "Developer",
    "system": "System",
    "unknown": "Unknown",
}
GROUP_MODES = ["none", "month", "project"]


def normalize_explorer_path(raw_path: str) -> str:
    path = raw_path.strip().strip('"').replace("\r", " ").replace("\n", " ")
    path = re.sub(r"\s+", " ", path)
    path = re.sub(r"^/abs/path/", "", path)
    path = re.sub(r"([/\\])\s+", r"\1", path)
    path = re.sub(r"\s+([/\\])", r"\1", path)
    windows_match = re.search(r"([A-Za-z]:[/\\][^\r\n]*)", path)
    if windows_match:
        path = windows_match.group(1)
    path = path.replace("/", "\\")
    path = re.sub(r"\\+", r"\\", path)
    return path.strip()


def open_in_explorer(raw_path: str):
    path = normalize_explorer_path(raw_path)
    if not path:
        return False
    target = Path(path)
    try:
        if target.exists():
            if target.is_file():
                subprocess.Popen(["explorer", "/select,", str(target)])
            else:
                os.startfile(str(target))
            return True
        parent = target.parent
        if parent.exists():
            os.startfile(str(parent))
            return True
    except Exception:
        return False
    return False


def simplify_project_name(preview: str | None, fallback_path: Path) -> str:
    if preview:
        match = WINDOWS_PATH_PATTERN.search(preview)
        if match:
            candidate = Path(match.group(0)).name.strip()
            if candidate:
                return candidate
        first_line = preview.splitlines()[0].strip()
        first_line = re.sub(r"\s+", " ", first_line)
        if first_line:
            return first_line[:60] + "..." if len(first_line) > 60 else first_line
    return fallback_path.stem


def detect_project_folder(preview: str | None) -> str | None:
    if not preview:
        return None
    match = WINDOWS_PATH_PATTERN.search(preview)
    if not match:
        return None
    candidate = Path(match.group(0))
    return str(candidate) if candidate.exists() else str(candidate)


def replace_project_root(path: str, original_root: str | None, new_root: str | None) -> str:
    normalized_path = normalize_explorer_path(path)
    normalized_original = normalize_explorer_path(original_root or "")
    normalized_new = normalize_explorer_path(new_root or "")
    if not normalized_path or not normalized_original or not normalized_new:
        return normalized_path
    if normalized_path.lower() == normalized_original.lower():
        return normalized_new
    prefix = normalized_original.rstrip("\\") + "\\"
    if not normalized_path.lower().startswith(prefix.lower()):
        return normalized_path
    suffix = normalized_path[len(prefix):]
    return normalized_new.rstrip("\\") + "\\" + suffix


class ProjectRemapDialog(ctk.CTkToplevel):
    def __init__(self, app, chat_relative: str, original_root: str, current_root: str | None):
        super().__init__(app)
        self.app = app
        self.chat_relative = chat_relative
        self.original_root = original_root
        self.title("Remap Project")
        self.geometry("760x300")
        self.minsize(720, 260)
        self.transient(app)
        self.grab_set()

        self.new_root_var = tk.StringVar(value=current_root or "")

        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Remap Project", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text="Save a replacement project root for this selected chat.",
            text_color=self.app.colors["muted"],
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        content = self.app.make_card(self)
        content.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 12))
        content.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(content, text="Chat").grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6))
        ctk.CTkLabel(content, text=chat_relative, text_color=self.app.colors["muted"], justify="left").grid(row=1, column=0, sticky="w", padx=16)

        ctk.CTkLabel(content, text="Original project root").grid(row=2, column=0, sticky="w", padx=16, pady=(14, 6))
        ctk.CTkLabel(content, text=original_root, text_color=self.app.colors["muted"], justify="left").grid(row=3, column=0, sticky="w", padx=16)

        ctk.CTkLabel(content, text="New project root").grid(row=4, column=0, sticky="w", padx=16, pady=(14, 6))
        entry_row = ctk.CTkFrame(content, fg_color="transparent")
        entry_row.grid(row=5, column=0, sticky="ew", padx=16, pady=(0, 16))
        entry_row.grid_columnconfigure(0, weight=1)
        self.new_root_entry = ctk.CTkEntry(entry_row, textvariable=self.new_root_var)
        self.new_root_entry.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(entry_row, text="Browse", width=92, command=self.pick_folder).grid(row=0, column=1, padx=(10, 0))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 18))
        footer.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(footer, text="Clear", fg_color="transparent", border_width=1, command=self.clear_remap).grid(row=0, column=1, padx=(10, 0))
        ctk.CTkButton(footer, text="Cancel", fg_color="transparent", border_width=1, command=self.destroy).grid(row=0, column=2, padx=(10, 0))
        ctk.CTkButton(footer, text="Save", command=self.save_remap).grid(row=0, column=3, padx=(10, 0))

    def pick_folder(self):
        selected = filedialog.askdirectory(initialdir=self.new_root_var.get() or self.original_root, parent=self)
        if selected:
            self.new_root_var.set(selected)

    def clear_remap(self):
        self.app.clear_chat_project_remap(self.chat_relative)
        self.destroy()

    def save_remap(self):
        new_root = normalize_explorer_path(self.new_root_var.get())
        if not new_root:
            messagebox.showerror("Invalid folder", "Choose or enter a valid project folder.")
            return
        if not Path(new_root).is_dir():
            messagebox.showerror("Folder not found", f"Could not find:\n{new_root}")
            return
        self.app.set_chat_project_remap(self.chat_relative, new_root)
        self.destroy()


class CodexViewerApp(ctk.CTk):
    MESSAGE_CHUNK_SIZE = 120

    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(WINDOW_SIZE)
        self.minsize(*MIN_WINDOW_SIZE)

        self.config = load_config()
        self._normalize_config()
        self.colors = self.get_active_palette(self.config)
        self.sessions_dir = get_codex_sessions_dir()

        self.files = []
        self.filtered_files = []
        self.list_tag_to_item = {}
        self.list_tag_ranges = {}
        self.line_to_row_tag = {}
        self.selected_row_tag = None
        self.parsed_cache = {}
        self.known_mtimes = {}
        self.selected_path = None
        self.selected_relative = None
        self.current_messages = []
        self.rendered_message_start = 0
        self.project_folder = None
        self.original_project_folder = None
        self.last_loaded_signature = None
        self.poll_after_id = None
        self.link_targets = {}
        self.link_counter = 0
        self.link_tooltip = None

        self.auto_refresh_var = tk.BooleanVar(value=self.config.get("auto_refresh_default", False))
        self.show_meta_var = tk.BooleanVar(value=self.config["show_meta_default"])
        self.search_var = tk.StringVar()
        self.group_var = tk.StringVar(value=self.config.get("group_mode", "none"))
        self.search_var.trace_add("write", lambda *_args: self.filter_file_list())

        self.apply_theme()
        self._build_ui()
        self.refresh_file_list(initial=True)
        self.schedule_poll()

    def _normalize_config(self):
        if "appearance_mode" not in self.config:
            self.config["appearance_mode"] = self.config.get("theme_mode", "dark")
        if "palette" not in self.config and "palette_dark" in self.config:
            self.config["palette"] = dict(self.config["palette_dark"])
        legacy_bracket_defaults = {
            "palette": {"#b388ff": "#7cb8ff"},
            "palette_light": {"#7a42d1": "#1f62d3"},
        }
        for palette_key, replacements in legacy_bracket_defaults.items():
            current_palette = self.config.get(palette_key, {})
            current_value = current_palette.get("bracket_link")
            if current_value in replacements:
                current_palette["bracket_link"] = replacements[current_value]
        if not self.config.get("accent_color"):
            self.config["accent_color"] = self.config[self._palette_key()]["accent"]
        self.config[self._palette_key()]["accent"] = self.config["accent_color"]
        self.config.setdefault("auto_refresh_default", False)
        self.config.setdefault("group_mode", "none")
        self.config.setdefault("chat_project_remaps", {})

    def _palette_key(self, config=None):
        current = config or self.config
        return "palette_light" if current.get("appearance_mode") == "light" else "palette"

    def get_active_palette(self, config=None):
        palette = get_active_palette(config or self.config)
        palette["accent"] = (config or self.config).get("accent_color", palette["accent"])
        return palette

    def make_card(self, master, corner_radius=22):
        return ctk.CTkFrame(master, fg_color=self.colors["surface"], border_width=1, border_color=self.colors["border"], corner_radius=corner_radius)

    def apply_theme(self):
        ctk.set_appearance_mode("dark" if self.config["appearance_mode"] == "dark" else "light")
        ctk.set_default_color_theme("blue")
        self.colors = self.get_active_palette(self.config)
        self.configure(fg_color=self.colors["bg"])

    def density_spacing(self, compact, balanced, relaxed):
        density = self.config.get("density", "balanced")
        if density == "compact":
            return compact
        if density == "relaxed":
            return relaxed
        return balanced

    def _build_ui(self):
        pad = self.density_spacing(14, 18, 24)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=pad, pady=(pad, 10))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=1)

        brand = ctk.CTkFrame(header, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(brand, text=APP_TITLE, font=ctk.CTkFont(size=28, weight="bold"), text_color=self.colors["text"]).pack(anchor="w")
        ctk.CTkLabel(brand, text="Fast, simple session browsing.", text_color=self.colors["muted"]).pack(anchor="w", pady=(4, 0))

        controls = self.make_card(header, corner_radius=20)
        controls.grid(row=0, column=1, sticky="e")
        self.refresh_switch = ctk.CTkSwitch(controls, text="Auto refresh", variable=self.auto_refresh_var)
        self.refresh_switch.grid(row=0, column=0, padx=(14, 10), pady=14)
        ctk.CTkButton(controls, text="Theme", width=86, command=self.toggle_theme).grid(row=0, column=1, padx=10, pady=14)
        ctk.CTkButton(controls, text="Settings", width=92, command=self.open_settings).grid(row=0, column=2, padx=10, pady=14)
        ctk.CTkButton(controls, text="Refresh", width=92, command=self.refresh_file_list).grid(row=0, column=3, padx=(10, 14), pady=14)

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew", padx=pad, pady=(0, pad))
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)

        self.sidebar = self.make_card(main)
        self.sidebar.grid(row=0, column=0, sticky="nsw", padx=(0, 12))
        self.sidebar.configure(width=380)
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(3, weight=1)
        self.sidebar.grid_columnconfigure(0, weight=1)

        sidebar_header = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        sidebar_header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        sidebar_header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(sidebar_header, text="Chats", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, sticky="w")
        self.chat_count_label = ctk.CTkLabel(sidebar_header, text="", text_color=self.colors["muted"])
        self.chat_count_label.grid(row=0, column=1, sticky="e")

        group_row = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        group_row.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        group_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(group_row, text="Group", text_color=self.colors["muted"]).grid(row=0, column=0, sticky="w")
        self.group_menu = ctk.CTkOptionMenu(group_row, values=GROUP_MODES, variable=self.group_var, command=self.change_group_mode)
        self.group_menu.grid(row=0, column=1, sticky="ew", padx=(10, 0))

        search_row = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        search_row.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 8))
        search_row.grid_columnconfigure(0, weight=1)
        self.search_entry = ctk.CTkEntry(search_row, textvariable=self.search_var, placeholder_text="Search chats")
        self.search_entry.grid(row=0, column=0, sticky="ew")

        list_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        list_frame.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 12))
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        self.file_list = tk.Text(
            list_frame,
            wrap="none",
            relief="flat",
            bd=0,
            highlightthickness=1,
            padx=10,
            pady=8,
            font=(self.config["font_family"], self.config["font_size"]),
            bg=self.colors["surface_alt"],
            fg=self.colors["text"],
            insertbackground=self.colors["text"],
            selectbackground=self.colors["selection"],
            yscrollcommand=lambda *args: self.file_yscroll.set(*args),
            cursor="arrow",
        )
        self.file_list.grid(row=0, column=0, sticky="nsew")
        self.file_list.bind("<Button-1>", self.on_select_file)
        self.file_list.bind("<MouseWheel>", self.scroll_list_fast)
        self.file_list.bind("<Key>", lambda _event: "break")
        self.file_list.bind("<<Paste>>", lambda _event: "break")
        self.file_list.bind("<<Cut>>", lambda _event: "break")
        self.file_yscroll = tk.Scrollbar(list_frame, orient="vertical", command=self.file_list.yview)
        self.file_yscroll.grid(row=0, column=1, sticky="ns")
        self.configure_list_tags()

        self.viewer = self.make_card(main)
        self.viewer.grid(row=0, column=1, sticky="nsew")
        self.viewer.grid_columnconfigure(0, weight=1)
        self.viewer.grid_rowconfigure(2, weight=1)

        top_controls = ctk.CTkFrame(self.viewer, fg_color="transparent")
        top_controls.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 8))
        top_controls.grid_columnconfigure(0, weight=1)
        self.chat_title = ctk.CTkLabel(top_controls, text="Select a chat", font=ctk.CTkFont(size=22, weight="bold"))
        self.chat_title.grid(row=0, column=0, sticky="w")
        self.meta_label = ctk.CTkLabel(top_controls, text="", text_color=self.colors["muted"], justify="left")
        self.meta_label.grid(row=1, column=0, sticky="w", pady=(6, 0))

        mid_controls = ctk.CTkFrame(self.viewer, fg_color="transparent")
        mid_controls.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))
        mid_controls.grid_columnconfigure(5, weight=1)
        self.load_older_button = ctk.CTkButton(mid_controls, text="Load older messages", width=180, command=self.load_older_messages)
        self.load_older_button.grid(row=0, column=0, sticky="w")
        self.load_older_button.grid_remove()
        self.open_project_button = ctk.CTkButton(mid_controls, text="Open project folder", width=160, command=self.open_project_folder)
        self.open_project_button.grid(row=0, column=1, padx=(10, 0), sticky="w")
        self.remap_project_button = ctk.CTkButton(mid_controls, text="Remap project", width=140, command=self.open_project_remap_dialog)
        self.remap_project_button.grid(row=0, column=2, padx=(10, 0), sticky="w")
        self.top_button = ctk.CTkButton(mid_controls, text="Top", width=70, command=self.scroll_to_top)
        self.top_button.grid(row=0, column=3, padx=(10, 0), sticky="w")
        self.bottom_button = ctk.CTkButton(mid_controls, text="Bottom", width=80, command=self.scroll_to_bottom)
        self.bottom_button.grid(row=0, column=4, padx=(10, 0), sticky="w")
        self.summary_label = ctk.CTkLabel(mid_controls, text="", text_color=self.colors["muted"])
        self.summary_label.grid(row=0, column=5, padx=(10, 0), sticky="e")

        viewer_frame = ctk.CTkFrame(self.viewer, fg_color="transparent")
        viewer_frame.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 14))
        viewer_frame.grid_rowconfigure(0, weight=1)
        viewer_frame.grid_columnconfigure(0, weight=1)

        self.text = tk.Text(
            viewer_frame,
            wrap="word",
            relief="flat",
            bd=0,
            padx=14,
            pady=14,
            font=(self.config["font_family"], self.config["font_size"]),
            bg=self.colors["surface_alt"],
            fg=self.colors["text"],
            insertbackground=self.colors["text"],
            selectbackground=self.colors["selection"],
            selectforeground=self.colors["text"],
            inactiveselectbackground=self.colors["selection"],
            yscrollcommand=lambda *args: self.text_yscroll.set(*args),
        )
        self.text.grid(row=0, column=0, sticky="nsew")
        self.text.bind("<MouseWheel>", self.scroll_viewer_fast)
        self.text.bind("<Control-c>", self.copy_selected_text)
        self.text.bind("<Control-C>", self.copy_selected_text)
        self.text.bind("<<Copy>>", self.copy_selected_text)
        self.text.bind("<Key>", lambda _event: "break")
        self.text.bind("<<Paste>>", lambda _event: "break")
        self.text.bind("<<Cut>>", lambda _event: "break")
        self.text_yscroll = tk.Scrollbar(viewer_frame, orient="vertical", command=self.text.yview)
        self.text_yscroll.grid(row=0, column=1, sticky="ns")
        self.configure_text_tags()
        self.show_empty_state("No chat selected", "Choose a chat from the left to start reading.")

    def configure_text_tags(self):
        body_font = (self.config["font_family"], self.config["font_size"])
        small_font = (self.config["font_family"], max(10, self.config["font_size"] - 1))
        self.text.tag_config("title", foreground=self.colors["text"], font=(self.config["font_family"], self.config["font_size"] + 1, "bold"))
        self.text.tag_config("meta", foreground=self.colors["muted"], font=small_font)
        self.text.tag_config("separator", foreground=self.colors["border"])
        self.text.tag_config("inline_code", foreground=self.colors["inline_code"], background=self.colors["code_bg"], font=("Consolas", self.config["font_size"]))
        self.text.tag_config("bracket_link", foreground=self.colors["bracket_link"], underline=True, font=body_font)
        self.text.tag_config("angle_token", foreground=self.colors["success"], font=("Consolas", self.config["font_size"]))
        self.text.tag_config("aborted_block", foreground=self.colors["danger"], font=body_font)
        self.text.tag_config("aborted_token", foreground=self.colors["danger"], font=("Consolas", self.config["font_size"], "bold"))
        role_bg = self.role_body_colors()
        for role in ROLE_LABELS:
            self.text.tag_config(f"{role}_header", foreground=self.colors[role], font=(self.config["font_family"], self.config["font_size"], "bold"), background=role_bg[role])
            self.text.tag_config(f"{role}_meta", foreground=self.colors["muted"], font=small_font, background=role_bg[role])
            self.text.tag_config(f"{role}_body", foreground=self.colors["text"], font=body_font, background=role_bg[role])
        self.text.tag_raise("aborted_block")
        self.text.tag_raise("aborted_token")
        self.text.tag_raise("inline_code")
        self.text.tag_raise("angle_token")
        self.text.tag_raise("bracket_link")
        self.text.tag_raise("sel")

    def role_body_colors(self):
        if self.config["appearance_mode"] == "light":
            return {
                "user": "#eef9f1",
                "assistant": "#eef4ff",
                "developer": "#fff6e5",
                "system": "#f7efff",
                "unknown": self.colors["surface_alt"],
            }
        return {
            "user": "#162c22",
            "assistant": "#162845",
            "developer": "#312714",
            "system": "#2a1d3d",
            "unknown": self.colors["surface_alt"],
        }

    def configure_list_tags(self):
        row_font = (self.config["font_family"], self.config["font_size"], "bold")
        group_font = (self.config["font_family"], self.config["font_size"] + 1, "bold")
        self.file_list.tag_config("group_header", foreground=self.colors["accent"], font=group_font, spacing1=2, spacing3=1)
        self.file_list.tag_config("row_title", foreground=self.colors["text"], font=row_font, spacing1=0, spacing3=0)
        self.file_list.tag_config("selected_row", background=self.colors["selection"])

    def clear_text(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", tk.END)
        for tag_name in list(self.link_targets):
            self.text.tag_delete(tag_name)
        self.link_targets.clear()
        self.link_counter = 0
        self.link_tooltip = None

    def show_empty_state(self, title, body):
        self.clear_text()
        self.text.insert("end", title + "\n", "title")
        self.text.insert("end", body + "\n", "meta")
        self.summary_label.configure(text="")
        self.open_project_button.configure(state="disabled")
        self.remap_project_button.configure(state="disabled", text="Remap project")

    def scroll_list_fast(self, event):
        self.file_list.yview_scroll(-3 if event.delta > 0 else 3, "units")
        return "break"

    def scroll_viewer_fast(self, event):
        self.text.yview_scroll(-3 if event.delta > 0 else 3, "units")
        return "break"

    def scroll_to_top(self):
        self.text.yview_moveto(0.0)

    def scroll_to_bottom(self):
        self.text.yview_moveto(1.0)

    def copy_selected_text(self, _event=None):
        try:
            selected_text = self.text.get("sel.first", "sel.last")
        except tk.TclError:
            return "break"
        self.clipboard_clear()
        self.clipboard_append(selected_text)
        self.update()
        return "break"

    def get_chat_project_remap(self, chat_relative: str | None = None) -> str | None:
        key = chat_relative or self.selected_relative
        if not key:
            return None
        remap = self.config.get("chat_project_remaps", {}).get(key)
        return normalize_explorer_path(remap) if remap else None

    def set_chat_project_remap(self, chat_relative: str, new_root: str):
        remaps = dict(self.config.get("chat_project_remaps", {}))
        remaps[chat_relative] = normalize_explorer_path(new_root)
        self.config["chat_project_remaps"] = remaps
        save_config(self.config)
        self.last_loaded_signature = None
        if self.selected_relative == chat_relative and self.selected_path and self.selected_path.exists():
            self.load_chat(self.selected_path)

    def clear_chat_project_remap(self, chat_relative: str):
        remaps = dict(self.config.get("chat_project_remaps", {}))
        if chat_relative in remaps:
            remaps.pop(chat_relative, None)
            self.config["chat_project_remaps"] = remaps
            save_config(self.config)
        self.last_loaded_signature = None
        if self.selected_relative == chat_relative and self.selected_path and self.selected_path.exists():
            self.load_chat(self.selected_path)

    def get_selected_original_project_root(self) -> str | None:
        return normalize_explorer_path(self.original_project_folder) if self.original_project_folder else None

    def get_effective_project_folder(self) -> str | None:
        original_root = self.get_selected_original_project_root()
        return self.get_chat_project_remap() or original_root

    def remap_selected_chat_path(self, raw_path: str) -> str:
        return replace_project_root(raw_path, self.get_selected_original_project_root(), self.get_chat_project_remap())

    def update_project_controls(self):
        has_original = bool(self.get_selected_original_project_root())
        has_remap = bool(self.get_chat_project_remap())
        effective_root = self.get_effective_project_folder()
        self.project_folder = effective_root
        self.open_project_button.configure(state="normal" if effective_root else "disabled")
        self.remap_project_button.configure(
            state="normal" if has_original else "disabled",
            text="Edit remap" if has_remap else "Remap project",
        )

    def open_project_remap_dialog(self):
        original_root = self.get_selected_original_project_root()
        if not (self.selected_relative and original_root):
            return
        ProjectRemapDialog(self, self.selected_relative, original_root, self.get_chat_project_remap())

    def schedule_poll(self):
        if self.poll_after_id is not None:
            self.after_cancel(self.poll_after_id)
        self.poll_after_id = self.after(self.config["poll_interval_ms"], self._poll_files)

    def _poll_files(self):
        if self.auto_refresh_var.get():
            self.refresh_file_list()
        self.schedule_poll()

    def change_group_mode(self, choice):
        self.config["group_mode"] = choice
        save_config(self.config)
        self.filter_file_list(restore_relative=self.selected_relative)

    def get_parsed_data(self, path: Path, mtime: float, size: int):
        key = str(path)
        cached = self.parsed_cache.get(key)
        if cached and cached["mtime"] == mtime and cached["size"] == size:
            return cached
        try:
            messages, preview, last_message_time, meta = parse_codex_file(path)
        except Exception:
            messages, preview, last_message_time, meta = [], None, None, {}
        parsed = {
            "mtime": mtime,
            "size": size,
            "messages": messages,
            "preview": preview,
            "last_message_time": last_message_time,
            "meta": meta,
            "project_folder": detect_project_folder(preview),
        }
        self.parsed_cache[key] = parsed
        return parsed

    def build_file_item(self, path: Path, initial: bool, now: float):
        try:
            stat = path.stat()
        except OSError:
            return None
        relative = path.relative_to(self.sessions_dir)
        parsed = self.get_parsed_data(path, stat.st_mtime, stat.st_size)
        date_label = parse_date_from_relative_path(relative)
        project_name = simplify_project_name(parsed["preview"], path)
        prev_mtime = self.known_mtimes.get(str(path))
        is_updated = prev_mtime is not None and stat.st_mtime > prev_mtime and (now - stat.st_mtime) <= self.config["updated_window_seconds"]
        if initial and (now - stat.st_mtime) <= self.config["updated_window_seconds"]:
            is_updated = True
        self.known_mtimes[str(path)] = stat.st_mtime
        return {
            "path": path,
            "relative": str(relative),
            "date": date_label,
            "project": project_name,
            "display": f"{date_label}: {project_name}",
            "subtitle": str(relative),
            "mtime": stat.st_mtime,
            "size": stat.st_size,
            "is_updated": is_updated,
            "messages_count": len(parsed["messages"]),
            "last_msg_time": parsed["last_message_time"],
            "project_folder": parsed["project_folder"],
        }

    def refresh_file_list(self, initial=False):
        if not self.sessions_dir.exists():
            self.files = []
            self.filtered_files = []
            self.file_list.delete("1.0", tk.END)
            self.chat_count_label.configure(text="0 shown")
            self.chat_title.configure(text="No sessions folder found")
            self.meta_label.configure(text="")
            self.summary_label.configure(text="")
            self.load_older_button.grid_remove()
            self.show_empty_state("No sessions folder found", "Create or point Codex at a sessions folder to populate the viewer.")
            return

        found = list(self.sessions_dir.rglob("*.jsonl"))
        if self.config.get("sort_mode") == "name":
            found.sort(key=lambda current: str(current).lower())
        else:
            found.sort(key=lambda current: current.stat().st_mtime, reverse=True)

        now = time.time()
        previous_selection = self.selected_relative
        new_entries = []
        alive_paths = set()
        for path in found:
            item = self.build_file_item(path, initial=initial, now=now)
            if item:
                new_entries.append(item)
                alive_paths.add(str(path))

        stale = [key for key in self.parsed_cache if key not in alive_paths]
        for key in stale:
            self.parsed_cache.pop(key, None)
            self.known_mtimes.pop(key, None)

        self.files = new_entries
        self.filter_file_list(restore_relative=previous_selection)
        if self.selected_path and self.selected_path.exists():
            self.reload_selected_chat()

    def build_group_key(self, item):
        mode = self.group_var.get()
        if mode == "project":
            return item["project"]
        if mode == "none":
            return None
        return item["date"][:7]

    def filter_file_list(self, restore_relative=None):
        query = self.search_var.get().strip().lower()
        self.filtered_files = []
        self.list_tag_to_item = {}
        self.list_tag_ranges = {}
        self.line_to_row_tag = {}
        restore_tag = None
        current_group = object()

        self.file_list.configure(state="normal")
        self.file_list.delete("1.0", tk.END)

        for item in self.files:
            haystack = f"{item['display']} {item['subtitle']}".lower()
            if query not in haystack:
                continue
            self.filtered_files.append(item)
            group_key = self.build_group_key(item)
            if group_key != current_group and group_key is not None:
                self.file_list.insert("end", f"{group_key}\n", ("group_header",))
                current_group = group_key

            row_tag = f"row_{len(self.list_tag_to_item)}"
            line_no = int(self.file_list.index("end-1c").split(".")[0])
            start = f"{line_no}.0"
            title = item["display"]
            if item["is_updated"]:
                title += "  [Updated]"
            self.file_list.insert("end", title + "\n", ("row_title", row_tag))
            end = f"{line_no}.end"
            self.list_tag_to_item[row_tag] = item
            self.list_tag_ranges[row_tag] = (start, end)
            self.line_to_row_tag[line_no] = row_tag
            if restore_relative and item["relative"] == restore_relative:
                restore_tag = row_tag
            elif self.selected_relative and item["relative"] == self.selected_relative:
                restore_tag = row_tag

        self.file_list.mark_set("insert", "1.0")
        self.chat_count_label.configure(text=f"{len(self.filtered_files)} shown")

        if restore_tag is not None and restore_tag in self.list_tag_to_item:
            self.apply_list_selection(restore_tag, scroll=True)
        elif not self.filtered_files:
            self.selected_row_tag = None

    def apply_list_selection(self, row_tag, scroll=False):
        if self.selected_row_tag and self.selected_row_tag in self.list_tag_ranges:
            start, end = self.list_tag_ranges[self.selected_row_tag]
            self.file_list.tag_remove("selected_row", start, end)
        self.selected_row_tag = row_tag
        if row_tag in self.list_tag_ranges:
            start, end = self.list_tag_ranges[row_tag]
            self.file_list.tag_add("selected_row", start, end)
            if scroll:
                self.file_list.see(start)

    def on_select_file(self, event=None):
        if event is None:
            return
        index = self.file_list.index(f"@{event.x},{event.y}")
        line_no = int(index.split(".")[0])
        row_tag = self.line_to_row_tag.get(line_no)
        if not row_tag:
            return "break"
        item = self.list_tag_to_item.get(row_tag)
        if item is None:
            return "break"
        self.apply_list_selection(row_tag)
        self.selected_path = item["path"]
        self.selected_relative = item["relative"]
        self.last_loaded_signature = None
        self.load_chat(item["path"])
        return "break"

    def format_link_label(self, label, raw_path):
        cleaned = raw_path.strip()
        match = re.search(r"#L(\d+)(?:C(\d+))?$", cleaned)
        if not match:
            return f"[{label}]"
        line = match.group(1)
        column = match.group(2)
        suffix = f":{line}"
        if column:
            suffix += f":{column}"
        return f"{label}{suffix}"

    def angle_token_tag(self, token_text):
        lowered = token_text.lower()
        if "turn_aborted" in lowered:
            return "aborted_token"
        return "angle_token"

    def insert_text_with_formatting(self, text, body_tag):
        pos = 0
        while pos < len(text):
            next_aborted = ABORTED_BLOCK_PATTERN.search(text, pos)
            next_bracket = BRACKET_PATH_PATTERN.search(text, pos)
            next_code = INLINE_CODE_PATTERN.search(text, pos)
            next_angle = ANGLE_TOKEN_PATTERN.search(text, pos)
            candidates = [m for m in (next_aborted, next_bracket, next_code, next_angle) if m]
            if not candidates:
                self.text.insert("end", text[pos:], body_tag)
                break
            match = min(candidates, key=lambda m: m.start())
            if match.start() > pos:
                self.text.insert("end", text[pos:match.start()], body_tag)
            if match.re is ABORTED_BLOCK_PATTERN:
                self.text.insert("end", match.group(0), (body_tag, "aborted_block"))
            elif match.re is BRACKET_PATH_PATTERN:
                path = match.group(2).strip()
                label_text = self.format_link_label(match.group(1), path)
                start = self.text.index("end")
                tag_name = f"link_{self.link_counter}"
                self.link_counter += 1
                self.text.insert("end", label_text, (body_tag, "bracket_link", tag_name))
                end = self.text.index("end")
                original_markup = match.group(0)
                self.link_targets[tag_name] = {"path": path, "original": original_markup}
                self.text.tag_add(tag_name, start, end)
                self.text.tag_bind(tag_name, "<Button-1>", lambda _event, target=path: self.on_link_click(target))
                self.text.tag_bind(tag_name, "<Enter>", lambda event, original=original_markup: self.on_link_enter(event, original))
                self.text.tag_bind(tag_name, "<Motion>", self.on_link_motion)
                self.text.tag_bind(tag_name, "<Leave>", self.on_link_leave)
            elif match.re is INLINE_CODE_PATTERN:
                self.text.insert("end", f"`{match.group(1)}`", (body_tag, "inline_code"))
            else:
                self.text.insert("end", match.group(0), (body_tag, self.angle_token_tag(match.group(0))))
            pos = match.end()

    def show_link_tooltip(self, x_root, y_root, text):
        self.hide_link_tooltip()
        tooltip = tk.Toplevel(self)
        tooltip.wm_overrideredirect(True)
        tooltip.configure(bg=self.colors["border"])
        tooltip.wm_geometry(f"+{x_root + 14}+{y_root + 14}")
        label = tk.Label(
            tooltip,
            text=text,
            justify="left",
            bg=self.colors["surface"],
            fg=self.colors["text"],
            bd=0,
            padx=8,
            pady=6,
            font=(self.config["font_family"], max(10, self.config["font_size"] - 1)),
        )
        label.pack(padx=1, pady=1)
        self.link_tooltip = tooltip

    def hide_link_tooltip(self):
        if self.link_tooltip is not None:
            self.link_tooltip.destroy()
            self.link_tooltip = None

    def on_link_enter(self, event, original_text):
        self.text.configure(cursor="hand2")
        self.show_link_tooltip(event.x_root, event.y_root, original_text)

    def on_link_motion(self, event):
        if self.link_tooltip is not None:
            self.link_tooltip.wm_geometry(f"+{event.x_root + 14}+{event.y_root + 14}")

    def on_link_leave(self, _event=None):
        self.text.configure(cursor="xterm")
        self.hide_link_tooltip()

    def on_link_click(self, path):
        resolved_path = self.remap_selected_chat_path(path)
        if not open_in_explorer(resolved_path):
            messagebox.showwarning("Path not found", f"Could not open:\n{resolved_path}")

    def render_text_messages(self):
        self.clear_text()
        visible_messages = self.current_messages[self.rendered_message_start:]
        total_visible = len(visible_messages)
        for index, msg in enumerate(visible_messages, 1):
            role = msg["role"] if msg["role"] in ROLE_LABELS else "unknown"
            header = ROLE_LABELS[role].upper()
            if msg.get("timestamp"):
                header += f"  {msg['timestamp']}"
            self.text.insert("end", f" {header} \n", f"{role}_header")
            self.text.insert("end", f" line {msg['line_num']} \n", f"{role}_meta")
            self.insert_text_with_formatting(msg["text"].rstrip(), f"{role}_body")
            self.text.insert("end", "\n", f"{role}_body")
            if index != total_visible:
                self.text.insert("end", "\n" + ("-" * 84) + "\n\n", "separator")

        if self.show_meta_var.get() and self.selected_path:
            parsed = self.parsed_cache.get(str(self.selected_path), {})
            meta = parsed.get("meta", {})
            last_message_time = parsed.get("last_message_time")
            self.text.insert("end", "\nMETA\n", "title")
            for key, value in meta.items():
                self.text.insert("end", f"{key}: {value}\n", "meta")
            if last_message_time:
                self.text.insert("end", f"last_message_time: {last_message_time}\n", "meta")

        self.text.see("end")

    def update_load_older_button(self):
        if self.rendered_message_start > 0:
            self.load_older_button.configure(text=f"Load older messages ({self.rendered_message_start} hidden)")
            self.load_older_button.grid()
        else:
            self.load_older_button.grid_remove()

    def load_older_messages(self):
        if self.rendered_message_start <= 0:
            return
        self.rendered_message_start = max(0, self.rendered_message_start - self.MESSAGE_CHUNK_SIZE)
        self.update_load_older_button()
        self.render_text_messages()

    def open_project_folder(self):
        project_folder = self.get_effective_project_folder()
        if project_folder:
            open_in_explorer(project_folder)

    def load_chat(self, path: Path):
        stat = path.stat()
        parsed = self.get_parsed_data(path, stat.st_mtime, stat.st_size)
        messages = parsed["messages"]
        preview = parsed["preview"]
        relative = path.relative_to(self.sessions_dir) if path.exists() else Path(path.name)
        date_label = parse_date_from_relative_path(relative if isinstance(relative, Path) else Path(relative))
        title = simplify_project_name(preview, path)
        self.chat_title.configure(text=f"{date_label}: {title}")
        self.original_project_folder = parsed.get("project_folder")
        self.update_project_controls()
        if self.show_meta_var.get():
            meta_lines = [str(path)]
            remapped_root = self.get_chat_project_remap()
            if remapped_root:
                meta_lines.append(f"remapped_project_root: {remapped_root}")
            self.meta_label.configure(text="\n".join(meta_lines))
        else:
            self.meta_label.configure(text="")
        self.summary_label.configure(text=f"{len(messages)} messages")

        if not messages:
            self.current_messages = []
            self.rendered_message_start = 0
            self.update_load_older_button()
            self.show_empty_state("No readable messages", "The selected file loaded, but no readable message items were found.")
            self.last_loaded_signature = (str(path), stat.st_mtime, stat.st_size, bool(self.show_meta_var.get()), self.get_chat_project_remap())
            return

        self.current_messages = messages
        self.rendered_message_start = max(0, len(messages) - self.MESSAGE_CHUNK_SIZE)
        self.update_load_older_button()
        self.render_text_messages()
        self.last_loaded_signature = (str(path), stat.st_mtime, stat.st_size, bool(self.show_meta_var.get()), self.get_chat_project_remap())

    def reload_selected_chat(self):
        if not (self.selected_path and self.selected_path.exists()):
            return
        stat = self.selected_path.stat()
        signature = (str(self.selected_path), stat.st_mtime, stat.st_size, bool(self.show_meta_var.get()), self.get_chat_project_remap())
        if signature == self.last_loaded_signature:
            return
        self.load_chat(self.selected_path)

    def apply_new_config(self, new_config):
        self.config = new_config
        self._normalize_config()
        save_config(self.config)
        self.show_meta_var.set(self.config["show_meta_default"])
        self.group_var.set(self.config.get("group_mode", "none"))
        self.last_loaded_signature = None
        self.rebuild_ui()

    def rebuild_ui(self):
        selected_path = self.selected_path
        selected_relative = self.selected_relative
        self.apply_theme()
        for child in self.winfo_children():
            child.destroy()
        self.selected_path = selected_path
        self.selected_relative = selected_relative
        self.current_messages = []
        self.rendered_message_start = 0
        self._build_ui()
        self.refresh_file_list()
        self.reload_selected_chat()
        self.schedule_poll()

    def toggle_theme(self):
        self.config["appearance_mode"] = "light" if self.config["appearance_mode"] == "dark" else "dark"
        self.config["accent_color"] = self.config[self._palette_key()]["accent"]
        save_config(self.config)
        self.last_loaded_signature = None
        self.rebuild_ui()

    def open_settings(self):
        SettingsDialog(self)


def main():
    app = CodexViewerApp()
    app.mainloop()












