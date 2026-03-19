import json
from pathlib import Path

APP_TITLE = "Codex Chat Viewer"
WINDOW_SIZE = "1480x920"
MIN_WINDOW_SIZE = (1180, 760)
CONFIG_FILE = Path.home() / ".codex_chat_viewer_config.json"
VALID_APPEARANCE_MODES = {"dark", "light"}
VALID_DENSITIES = {"compact", "balanced", "relaxed"}
VALID_SORT_MODES = {"recent", "name"}
VALID_GROUP_MODES = {"none", "month", "project"}

DEFAULT_CONFIG = {
    "appearance_mode": "dark",
    "auto_refresh_default": False,
    "poll_interval_ms": 3000,
    "updated_window_seconds": 90,
    "show_meta_default": False,
    "font_family": "Segoe UI",
    "font_size": 13,
    "density": "balanced",
    "sort_mode": "recent",
    "group_mode": "none",
    "accent_color": "#4c8bf5",
    "palette": {
        "bg": "#0b1220",
        "surface": "#111a2b",
        "surface_alt": "#162238",
        "surface_soft": "#1b2942",
        "border": "#23324d",
        "text": "#edf3ff",
        "muted": "#8ea2c8",
        "accent": "#4c8bf5",
        "accent_soft": "#1e3a67",
        "success": "#38b26d",
        "warning": "#f2a65a",
        "danger": "#ff6b6b",
        "user": "#7ee787",
        "assistant": "#7cb8ff",
        "developer": "#ffd479",
        "system": "#d7b3ff",
        "unknown": "#c7d2e5",
        "code_bg": "#0f1727",
        "selection": "#203556",
        "inline_code": "#ffb86b",
        "bracket_link": "#7cb8ff",
    },
    "palette_light": {
        "bg": "#eef3fb",
        "surface": "#ffffff",
        "surface_alt": "#f5f8fc",
        "surface_soft": "#eaf0f9",
        "border": "#d7dfec",
        "text": "#172033",
        "muted": "#637089",
        "accent": "#2f6fed",
        "accent_soft": "#dbe7ff",
        "success": "#218554",
        "warning": "#ad6b00",
        "danger": "#c74b55",
        "user": "#16794f",
        "assistant": "#1f62d3",
        "developer": "#9b6500",
        "system": "#7847c9",
        "unknown": "#33415c",
        "code_bg": "#edf2fa",
        "selection": "#d9e6ff",
        "inline_code": "#ad5d00",
        "bracket_link": "#1f62d3",
    },
}


def clone_default_config():
    return json.loads(json.dumps(DEFAULT_CONFIG))


def deep_merge(base, override):
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _normalize_int(value, default, minimum):
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, normalized)


def normalize_config_values(config):
    normalized = dict(config)
    normalized["appearance_mode"] = normalized.get("appearance_mode") if normalized.get("appearance_mode") in VALID_APPEARANCE_MODES else DEFAULT_CONFIG["appearance_mode"]
    normalized["density"] = normalized.get("density") if normalized.get("density") in VALID_DENSITIES else DEFAULT_CONFIG["density"]
    normalized["sort_mode"] = normalized.get("sort_mode") if normalized.get("sort_mode") in VALID_SORT_MODES else DEFAULT_CONFIG["sort_mode"]
    normalized["group_mode"] = normalized.get("group_mode") if normalized.get("group_mode") in VALID_GROUP_MODES else DEFAULT_CONFIG["group_mode"]
    normalized["font_size"] = _normalize_int(normalized.get("font_size"), DEFAULT_CONFIG["font_size"], minimum=8)
    normalized["poll_interval_ms"] = _normalize_int(normalized.get("poll_interval_ms"), DEFAULT_CONFIG["poll_interval_ms"], minimum=500)
    normalized["updated_window_seconds"] = _normalize_int(normalized.get("updated_window_seconds"), DEFAULT_CONFIG["updated_window_seconds"], minimum=1)
    normalized["auto_refresh_default"] = bool(normalized.get("auto_refresh_default", DEFAULT_CONFIG["auto_refresh_default"]))
    normalized["show_meta_default"] = bool(normalized.get("show_meta_default", DEFAULT_CONFIG["show_meta_default"]))
    return normalized


def load_config():
    if not CONFIG_FILE.exists():
        return clone_default_config()
    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as handle:
            user_cfg = json.load(handle)
    except Exception:
        return clone_default_config()
    return normalize_config_values(deep_merge(clone_default_config(), user_cfg))


def save_config(config):
    with CONFIG_FILE.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)


def get_codex_sessions_dir() -> Path:
    return Path.home() / ".codex" / "sessions"


def get_active_palette(config):
    if config.get("appearance_mode") == "light":
        return config["palette_light"]
    return config["palette"]
