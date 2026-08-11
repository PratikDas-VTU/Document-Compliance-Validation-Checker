import json
import os
from app.utils.path_helper import get_base_path, get_data_dir

THEMES = {
    "Dark": {
        "APP_BG": "#0B0F14",
        "CARD_BG": "#111827",
        "ROW_BG": "#151E2D",
        "BORDER": "#243244",
        "ACCENT": "#3B82F6",
        "SUCCESS": "#22C55E",
        "WARNING": "#F59E0B",
        "CRITICAL": "#EF4444",
        "TEXT_PRIMARY": "#F8FAFC",
        "TEXT_SECONDARY": "#CBD5E1",
        "TEXT_MUTED": "#94A3B8",
        "SIDEBAR_BG": "#111827",
        "SIDEBAR_HOVER": "#151E2D"
    },
    "Light": {
        "APP_BG": "#F8FAFC",
        "CARD_BG": "#FFFFFF",
        "ROW_BG": "#F1F5F9",
        "BORDER": "#E2E8F0",
        "ACCENT": "#2563EB",
        "SUCCESS": "#16A34A",
        "WARNING": "#D97706",
        "CRITICAL": "#DC2626",
        "TEXT_PRIMARY": "#0F172A",
        "TEXT_SECONDARY": "#475569",
        "TEXT_MUTED": "#64748B",
        "SIDEBAR_BG": "#FFFFFF",
        "SIDEBAR_HOVER": "#F1F5F9"
    },
    "Midnight Pro": {
        "APP_BG": "#050505",
        "CARD_BG": "#111111",
        "ROW_BG": "#1A1A1A",
        "BORDER": "#252525",
        "ACCENT": "#00D4FF",
        "SUCCESS": "#00FFB3",
        "WARNING": "#F59E0B",
        "CRITICAL": "#EF4444",
        "TEXT_PRIMARY": "#F8FAFC",
        "TEXT_SECONDARY": "#94A3B8",
        "TEXT_MUTED": "#64748B",
        "SIDEBAR_BG": "#0A0A0A",
        "SIDEBAR_HOVER": "#1A1A1A"
    }
}

class ThemeManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ThemeManager, cls).__new__(cls)
            cls._instance.settings_file = os.path.join(get_data_dir(), "settings.json")
            cls._instance.settings = cls._instance._load()
            
            dirty = False
            if "appearance_mode" not in cls._instance.settings:
                cls._instance.settings["appearance_mode"] = "System"
                dirty = True
            if "theme" not in cls._instance.settings:
                cls._instance.settings["theme"] = "Dark"
                dirty = True
            if dirty:
                cls._instance.save()

            cls._instance._resolve_theme()
        return cls._instance

    def _resolve_theme(self):
        mode = self.settings.get("appearance_mode", "System")
        saved_theme = self.settings.get("theme", "Dark")
        if saved_theme not in THEMES:
            saved_theme = "Dark"
            
        if mode == "System":
            try:
                import darkdetect
                sys_theme = darkdetect.theme()
            except Exception:
                sys_theme = "Dark"
            if sys_theme == "Light":
                self.current_theme = "Light"
            else:
                self.current_theme = "Dark"
        elif mode == "Light":
            self.current_theme = "Light"
        else:
            self.current_theme = saved_theme if saved_theme != "Light" else "Dark"

    def _load(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save(self):
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
        except Exception:
            pass

    def get_theme_name(self):
        return self.current_theme

    def set_theme(self, name):
        if name in THEMES:
            self.settings["theme"] = name
            if name == "Light":
                self.settings["appearance_mode"] = "Light"
            else:
                self.settings["appearance_mode"] = "Dark"
            self.save()
            self._resolve_theme()

    def set_appearance_mode(self, mode):
        self.settings["appearance_mode"] = mode
        if mode == "Light":
            self.settings["theme"] = "Light"
        elif mode == "Dark":
            if self.settings.get("theme", "Dark") == "Light":
                self.settings["theme"] = "Dark"
        self.save()
        self._resolve_theme()

    def get_color(self, key):
        return THEMES[self.current_theme].get(key, "#000000")

    def get_setting(self, key, default=None):
        return self.settings.get(key, default)

    def set_setting(self, key, value):
        self.settings[key] = value
        self.save()

# Singleton instance
TM = ThemeManager()

# Global styling constants
RADIUS = 14
BORDER_WIDTH = 1
FONT_FAMILY = "Segoe UI"

def get_color(key: str) -> str:
    """Helper function to fetch the current theme's color."""
    return TM.get_color(key)

def get_font_h1():
    """Page Titles"""
    import customtkinter as ctk
    return ctk.CTkFont(family=FONT_FAMILY, size=28, weight="bold")

def get_font_h2():
    """Section Titles"""
    import customtkinter as ctk
    return ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold")

def get_font_h3():
    """Card Titles"""
    import customtkinter as ctk
    return ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold")

def get_font_body(weight="normal"):
    """Standard text"""
    import customtkinter as ctk
    return ctk.CTkFont(family=FONT_FAMILY, size=13, weight=weight)

def get_font_caption(weight="normal"):
    """Metadata, subtext, dates"""
    import customtkinter as ctk
    return ctk.CTkFont(family=FONT_FAMILY, size=11, weight=weight)
