"""
main_window.py — Main application window with sidebar navigation.
Uses CustomTkinter for a professional dark/light themed enterprise UI.
All navigation is instant (no blocking). Pages are pre-built and toggled.
"""
from __future__ import annotations
import customtkinter as ctk
from typing import Dict
from app.ui.theme import get_color, get_font_h1, get_font_h2, get_font_h3, get_font_body, get_font_caption, RADIUS, BORDER_WIDTH

SIDEBAR_W = 220

class MainWindow(ctk.CTk):
    """Root application window."""

    def __init__(self) -> None:
        super().__init__()

        # Window setup
        self.title("Document Compliance & Validation Checker")
        self.geometry("1280x780")
        self.minsize(1100, 680)

        # Load window icon defensively
        try:
            import os
            from app.utils.path_helper import get_icon_path
            icon_path = get_icon_path()
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

        # NOTE: appearance_mode and color_theme are already set in main() before
        # this window is created. Calling them again here would trigger a redundant
        # redraw flash — so we intentionally do NOT repeat those calls.
        from app.ui.theme import TM

        self._current_page: str = ""
        self._nav_buttons: Dict[str, ctk.CTkButton] = {}
        self._pages: Dict[str, ctk.CTkFrame] = {}
        self.active_scan_page = None

        # Timing tracking variables
        self.last_switch_ms = 0.0
        self.average_switch_ms = 0.0
        self.worst_switch_ms = 0.0
        self._total_switches = 0
        self._sum_switches = 0.0
        self._initialized_nav = False

        # Pre-cache reference logo fingerprints in background
        try:
            from app.services.branding_engine import BrandingEngine
            BrandingEngine()
        except Exception:
            pass

        self._build_layout()
        self._load_pages()
        # Resolve geometry before revealing the first page to avoid a 1-frame flash
        self.update_idletasks()
        self.show_page("dashboard")

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self._sidebar = ctk.CTkFrame(self, width=SIDEBAR_W, fg_color=get_color("SIDEBAR_BG"), corner_radius=0)
        self._sidebar.grid(row=0, column=0, sticky="nsew")
        self._sidebar.grid_propagate(False)
        self._sidebar.grid_rowconfigure(10, weight=1)

        # App logo / name
        logo_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        logo_frame.grid(row=0, column=0, padx=20, pady=(28, 8), sticky="ew")

        # Load and set sidebar logo
        try:
            import os
            from PIL import Image
            from app.utils.path_helper import get_assets_path
            logo_path = get_assets_path("app_logo.png")
            if os.path.exists(logo_path):
                pil_logo = Image.open(logo_path)
                self._sidebar_logo_img = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(28, 28))
                self._sidebar_logo_lbl = ctk.CTkLabel(logo_frame, image=self._sidebar_logo_img, text="")
                self._sidebar_logo_lbl.pack(side="left", padx=(0, 8))
            else:
                ctk.CTkLabel(logo_frame, text="⚙", font=get_font_h1(), text_color=get_color("ACCENT")).pack(side="left", padx=(0, 8))
        except Exception:
            ctk.CTkLabel(logo_frame, text="⚙", font=get_font_h1(), text_color=get_color("ACCENT")).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            logo_frame,
            text="ComplianceCheck",
            font=get_font_h2(),
            text_color=get_color("TEXT_PRIMARY"),
        ).pack(side="left")

        # Divider
        ctk.CTkFrame(self._sidebar, height=1, fg_color=get_color("BORDER")).grid(
            row=1, column=0, sticky="ew", padx=16, pady=(4, 12)
        )

        # Nav label
        ctk.CTkLabel(
            self._sidebar,
            text="NAVIGATION",
            font=get_font_caption("bold"),
            text_color=get_color("TEXT_SECONDARY"),
        ).grid(row=2, column=0, padx=20, pady=(0, 8), sticky="w")

        # Nav buttons
        NAV_ITEMS = [
            ("dashboard",             "  Dashboard",             "🏠"),
            ("scan",                  "  Scan Center",           "🔍"),
            ("rules",                 "  Rules Engine",          "📋"),
            ("reports",               "  Reports",               "📁"),
            ("developer_diagnostics", "  Developer Diagnostics", "🛠️"),
            ("settings",              "  Settings",              "⚙️"),
        ]

        for row_idx, (page_key, label, icon) in enumerate(NAV_ITEMS, start=3):
            btn = ctk.CTkButton(
                self._sidebar,
                text=f"{icon}  {label.strip()}",
                anchor="w",
                height=44,
                corner_radius=8,
                fg_color="transparent",
                hover_color=get_color("SIDEBAR_HOVER"),
                text_color=get_color("TEXT_SECONDARY"),
                font=get_font_body(),
                command=lambda k=page_key: self.show_page(k),
            )
            btn.grid(row=row_idx, column=0, padx=12, pady=6, sticky="ew")
            self._nav_buttons[page_key] = btn

        # Version label at bottom
        ctk.CTkLabel(
            self._sidebar,
            text="v1.0.0  •  Offline",
            font=get_font_caption(),
            text_color=get_color("TEXT_SECONDARY"),
        ).grid(row=11, column=0, padx=20, pady=(0, 16), sticky="sw")

        # Main content area
        self._content = ctk.CTkFrame(self, fg_color=get_color("APP_BG"), corner_radius=0)
        self._content.grid(row=0, column=1, sticky="nsew")
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_rowconfigure(0, weight=1)

    # ── Page Management ───────────────────────────────────────────────────────
    def _load_pages(self) -> None:
        """Lazily import and instantiate pages to keep startup fast."""
        from app.ui.dashboard import DashboardPage
        from app.ui.scan_page import ScanPage
        from app.ui.rules_page import RulesPage
        from app.ui.reports_page import ReportsPage
        from app.ui.developer_diagnostics import DeveloperDiagnosticsPage
        from app.ui.settings_page import SettingsPage

        page_classes = {
            "dashboard":             DashboardPage,
            "scan":                  ScanPage,
            "rules":                 RulesPage,
            "reports":               ReportsPage,
            "developer_diagnostics": DeveloperDiagnosticsPage,
            "settings":              SettingsPage,
        }

        for key, cls in page_classes.items():
            frame = cls(self._content, main_window=self)
            frame.grid(row=0, column=0, sticky="nsew")
            self._pages[key] = frame

    def show_page(self, key: str) -> None:
        """Switch visible page and highlight the active nav button."""
        if key not in self._pages:
            return

        import time
        start_t = time.perf_counter()

        # Update nav button styles
        for k, btn in self._nav_buttons.items():
            if k == key:
                btn.configure(
                    fg_color=get_color("SIDEBAR_HOVER"),
                    text_color=get_color("ACCENT"),
                    font=get_font_body("bold"),
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=get_color("TEXT_SECONDARY"),
                    font=get_font_body(),
                )

        # Raise the selected page to front
        self._pages[key].tkraise()
        self._current_page = key

        duration_ms = (time.perf_counter() - start_t) * 1000.0

        if self._initialized_nav:
            self.last_switch_ms = duration_ms
            self._total_switches += 1
            self._sum_switches += duration_ms
            self.average_switch_ms = self._sum_switches / self._total_switches
            if duration_ms > self.worst_switch_ms:
                self.worst_switch_ms = duration_ms
        else:
            self._initialized_nav = True

        # Notify pages that they have been shown
        page = self._pages[key]
        if hasattr(page, "on_show"):
            page.on_show()

    def navigate_to(self, key: str) -> None:
        """Public shortcut for inter-page navigation."""
        self.show_page(key)

    def rebuild_ui(self, return_to: str = "settings") -> None:
        """
        Destroys and rebuilds the entire UI to apply new themes.
        Uses withdraw/deiconify to suppress the visual flash during reconstruction.
        """
        # Hide the window during reconstruction to eliminate flickering
        self.withdraw()

        # Pre-apply the new background so there is no colour mismatch on reveal
        self.configure(fg_color=get_color("APP_BG"))

        # Save page states before destruction
        saved_states = {}
        for key, page in self._pages.items():
            if hasattr(page, "get_state"):
                try:
                    saved_states[key] = page.get_state()
                except Exception as e:
                    print(f"Error saving state for {key}: {e}")

        # Destroy existing widgets cleanly
        for widget in self.winfo_children():
            widget.destroy()

        self._nav_buttons.clear()
        self._pages.clear()

        # Re-initialise navigation timing parameters
        self._initialized_nav = False

        # Rebuild the full widget hierarchy
        self._build_layout()
        self._load_pages()

        # Restore page states
        for key, page in self._pages.items():
            if key in saved_states and hasattr(page, "set_state"):
                try:
                    page.set_state(saved_states[key])
                except Exception as e:
                    print(f"Error restoring state for {key}: {e}")

        # Resolve all geometry before making the window visible again
        self.update_idletasks()
        self.show_page(return_to)

        # Reveal the fully-rendered window — no flash visible to the user
        self.deiconify()
