import copy
import customtkinter as ctk
from tkinter import colorchooser, messagebox

from codex_viewer.config import DEFAULT_CONFIG


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Settings")
        self.geometry("760x680")
        self.minsize(700, 620)
        self.transient(app)
        self.grab_set()

        self.temp_config = copy.deepcopy(app.config)
        self.palette = self.app.get_active_palette(self.temp_config)
        self.swatches = {}

        self._build()
        self._sync_from_config()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Settings",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text="Adjust appearance, reading comfort, refresh behavior, and advanced colors.",
            text_color=self.app.colors["muted"],
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        tabs = ctk.CTkTabview(self)
        tabs.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 12))
        tabs.add("Appearance")
        tabs.add("Reading")
        tabs.add("Refresh")
        tabs.add("Advanced")

        for tab_name in ("Appearance", "Reading", "Refresh", "Advanced"):
            tabs.tab(tab_name).grid_columnconfigure(0, weight=1)

        self._build_appearance_tab(tabs.tab("Appearance"))
        self._build_reading_tab(tabs.tab("Reading"))
        self._build_refresh_tab(tabs.tab("Refresh"))
        self._build_advanced_tab(tabs.tab("Advanced"))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 18))
        footer.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(footer, text="", text_color=self.app.colors["muted"])
        self.status_label.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(footer, text="Reset current theme", command=self._reset_theme).grid(row=0, column=1, padx=(10, 0))
        ctk.CTkButton(footer, text="Cancel", fg_color="transparent", border_width=1, command=self.destroy).grid(row=0, column=2, padx=(10, 0))
        ctk.CTkButton(footer, text="Save", command=self._save).grid(row=0, column=3, padx=(10, 0))

    def _build_appearance_tab(self, tab):
        card = self.app.make_card(tab)
        card.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="Appearance mode").grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))
        self.appearance_menu = ctk.CTkOptionMenu(card, values=["dark", "light"], command=self._on_appearance_change)
        self.appearance_menu.grid(row=0, column=1, sticky="e", padx=16, pady=(16, 8))

        ctk.CTkLabel(card, text="Accent color").grid(row=1, column=0, sticky="w", padx=16, pady=8)
        self.accent_preview = ctk.CTkFrame(card, width=44, height=28, corner_radius=14)
        self.accent_preview.grid(row=1, column=1, sticky="e", padx=16, pady=8)
        self.accent_button = ctk.CTkButton(card, text="Pick accent", width=130, command=self._pick_accent)
        self.accent_button.grid(row=1, column=1, sticky="e", padx=(0, 72), pady=8)

        ctk.CTkLabel(card, text="Density").grid(row=2, column=0, sticky="w", padx=16, pady=(8, 16))
        self.density_menu = ctk.CTkOptionMenu(card, values=["compact", "balanced", "relaxed"])
        self.density_menu.grid(row=2, column=1, sticky="e", padx=16, pady=(8, 16))

    def _build_reading_tab(self, tab):
        card = self.app.make_card(tab)
        card.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="Font family").grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))
        self.font_family_entry = ctk.CTkEntry(card)
        self.font_family_entry.grid(row=0, column=1, sticky="ew", padx=16, pady=(16, 8))

        ctk.CTkLabel(card, text="Font size").grid(row=1, column=0, sticky="w", padx=16, pady=8)
        self.font_size_entry = ctk.CTkEntry(card)
        self.font_size_entry.grid(row=1, column=1, sticky="ew", padx=16, pady=8)

        ctk.CTkLabel(card, text="Show file meta by default").grid(row=2, column=0, sticky="w", padx=16, pady=(8, 16))
        self.show_meta_switch = ctk.CTkSwitch(card, text="")
        self.show_meta_switch.grid(row=2, column=1, sticky="e", padx=16, pady=(8, 16))

    def _build_refresh_tab(self, tab):
        card = self.app.make_card(tab)
        card.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="Refresh interval (ms)").grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))
        self.poll_entry = ctk.CTkEntry(card)
        self.poll_entry.grid(row=0, column=1, sticky="ew", padx=16, pady=(16, 8))

        ctk.CTkLabel(card, text="Updated badge duration (s)").grid(row=1, column=0, sticky="w", padx=16, pady=8)
        self.updated_entry = ctk.CTkEntry(card)
        self.updated_entry.grid(row=1, column=1, sticky="ew", padx=16, pady=8)

        ctk.CTkLabel(card, text="Sort chats by").grid(row=2, column=0, sticky="w", padx=16, pady=(8, 16))
        self.sort_menu = ctk.CTkOptionMenu(card, values=["recent", "name"])
        self.sort_menu.grid(row=2, column=1, sticky="e", padx=16, pady=(8, 16))

    def _build_advanced_tab(self, tab):
        intro = self.app.make_card(tab)
        intro.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        intro.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            intro,
            text="Advanced theme colors",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(
            intro,
            text="Use these only when the main theme controls are not enough. Changes apply to the active appearance mode only.",
            text_color=self.app.colors["muted"],
            justify="left",
        ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 16))

        self.advanced_list = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.advanced_list.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        tab.grid_rowconfigure(1, weight=1)

        color_keys = [
            ("bg", "Window background"),
            ("surface", "Primary card"),
            ("surface_alt", "Secondary card"),
            ("surface_soft", "Soft panel"),
            ("border", "Borders"),
            ("text", "Main text"),
            ("muted", "Muted text"),
            ("accent", "Accent"),
            ("accent_soft", "Soft accent"),
            ("success", "Success"),
            ("warning", "Warning"),
            ("danger", "Danger"),
            ("user", "User role"),
            ("assistant", "Assistant role"),
            ("developer", "Developer role"),
            ("system", "System role"),
            ("unknown", "Unknown role"),
            ("code_bg", "Code background"),
            ("selection", "Selection"),
            ("bracket_link", "Bracket link"),
        ]

        for row_index, (key, label) in enumerate(color_keys):
            row = self.app.make_card(self.advanced_list, corner_radius=18)
            row.grid(row=row_index, column=0, sticky="ew", pady=6)
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row, text=label).grid(row=0, column=0, sticky="w", padx=14, pady=12)
            swatch = ctk.CTkFrame(row, width=48, height=28, corner_radius=14)
            swatch.grid(row=0, column=1, sticky="e", padx=(0, 12), pady=12)
            ctk.CTkButton(row, text="Pick", width=80, command=lambda name=key: self._pick_color(name)).grid(row=0, column=2, padx=(0, 14), pady=12)
            self.swatches[key] = swatch

    def _sync_from_config(self):
        self.appearance_menu.set(self.temp_config["appearance_mode"])
        self.density_menu.set(self.temp_config["density"])
        self.sort_menu.set(self.temp_config["sort_mode"])
        self.show_meta_switch.select() if self.temp_config["show_meta_default"] else self.show_meta_switch.deselect()

        self.font_family_entry.delete(0, "end")
        self.font_family_entry.insert(0, self.temp_config["font_family"])
        self.font_size_entry.delete(0, "end")
        self.font_size_entry.insert(0, str(self.temp_config["font_size"]))
        self.poll_entry.delete(0, "end")
        self.poll_entry.insert(0, str(self.temp_config["poll_interval_ms"]))
        self.updated_entry.delete(0, "end")
        self.updated_entry.insert(0, str(self.temp_config["updated_window_seconds"]))

        self._refresh_theme_preview()

    def _on_appearance_change(self, _choice):
        self.temp_config["appearance_mode"] = self.appearance_menu.get()
        self.palette = self.app.get_active_palette(self.temp_config)
        self._refresh_theme_preview()
        self.status_label.configure(text="Theme preview updated for the selected appearance mode.")

    def _refresh_theme_preview(self):
        self.palette = self.app.get_active_palette(self.temp_config)
        self.accent_preview.configure(fg_color=self.palette["accent"])
        for key, swatch in self.swatches.items():
            swatch.configure(fg_color=self.palette[key])

    def _pick_accent(self):
        chosen = colorchooser.askcolor(color=self.palette["accent"], title="Pick accent color")
        if chosen and chosen[1]:
            self.palette["accent"] = chosen[1]
            self.temp_config["accent_color"] = chosen[1]
            self._refresh_theme_preview()

    def _pick_color(self, key):
        chosen = colorchooser.askcolor(color=self.palette[key], title=f"Pick color for {key}")
        if chosen and chosen[1]:
            self.palette[key] = chosen[1]
            self._refresh_theme_preview()

    def _reset_theme(self):
        target_key = "palette_light" if self.appearance_menu.get() == "light" else "palette"
        self.temp_config[target_key] = copy.deepcopy(DEFAULT_CONFIG[target_key])
        self.temp_config["accent_color"] = self.temp_config[target_key]["accent"]
        self._refresh_theme_preview()
        self.status_label.configure(text="Current theme palette reset to defaults.")

    def _save(self):
        try:
            self.temp_config["appearance_mode"] = self.appearance_menu.get()
            self.temp_config["density"] = self.density_menu.get()
            self.temp_config["sort_mode"] = self.sort_menu.get()
            self.temp_config["show_meta_default"] = bool(self.show_meta_switch.get())
            self.temp_config["font_family"] = self.font_family_entry.get().strip() or "Segoe UI"
            self.temp_config["font_size"] = int(self.font_size_entry.get())
            self.temp_config["poll_interval_ms"] = int(self.poll_entry.get())
            self.temp_config["updated_window_seconds"] = int(self.updated_entry.get())
        except ValueError:
            messagebox.showerror("Invalid settings", "Font size, refresh interval, and updated duration must be numbers.")
            return

        self.app.apply_new_config(self.temp_config)
        self.destroy()
