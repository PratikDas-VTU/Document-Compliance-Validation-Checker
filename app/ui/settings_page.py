"""
settings_page.py — Application Settings & Theme Selection.
Phase 5D: Added Application Data maintenance section.
"""
import os
import json
import customtkinter as ctk
from tkinter import filedialog
from app.ui.theme import (
    TM, get_color, get_font_h1, get_font_h2, get_font_h3,
    get_font_body, get_font_caption, RADIUS, BORDER_WIDTH,
)
from app.ui.components import CustomDialog
from app.utils.path_helper import get_reports_dir, get_data_dir


class SettingsPage(ctk.CTkFrame):
    def __init__(self, parent, main_window, **kwargs):
        print("Settings Page Created")
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._main_window = main_window

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.grid(row=0, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        self._build()

    def _build(self):
        S = self._scroll

        # ── Header ─────────────────────────────────────────────────────────
        ctk.CTkLabel(
            S, text="Platform Settings",
            font=get_font_h1(), text_color=get_color("TEXT_PRIMARY"),
        ).grid(row=0, column=0, padx=32, pady=(28, 4), sticky="w")

        ctk.CTkLabel(
            S, text="Configure global platform appearance and maintenance options.",
            font=get_font_body(), text_color=get_color("TEXT_SECONDARY"),
        ).grid(row=1, column=0, padx=32, pady=(0, 24), sticky="w")

        # ── Appearance Card ─────────────────────────────────────────────────
        app_card = ctk.CTkFrame(
            S, fg_color=get_color("CARD_BG"), corner_radius=RADIUS,
            border_width=BORDER_WIDTH, border_color=get_color("BORDER"),
        )
        app_card.grid(row=2, column=0, padx=32, pady=(0, 24), sticky="ew")
        app_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            app_card, text="Appearance",
            font=get_font_h2(), text_color=get_color("TEXT_PRIMARY"),
        ).grid(row=0, column=0, padx=24, pady=(20, 12), sticky="w")

        # Theme Selector
        row1 = ctk.CTkFrame(app_card, fg_color="transparent")
        row1.grid(row=1, column=0, padx=24, pady=(0, 20), sticky="ew")
        row1.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            row1, text="Global Theme",
            font=get_font_h3(), text_color=get_color("TEXT_PRIMARY"),
        ).grid(row=0, column=0, sticky="w", pady=4)

        ctk.CTkLabel(
            row1, text="Select your preferred color scheme for the platform.",
            font=get_font_body(), text_color=get_color("TEXT_SECONDARY"),
        ).grid(row=1, column=0, sticky="w")

        themes = ["Midnight Pro", "Dark", "Light"]
        self.theme_var = ctk.StringVar(value=TM.get_theme_name())
        self.combo = ctk.CTkOptionMenu(
            row1, values=themes, variable=self.theme_var,
            command=self._on_theme_changed,
            font=get_font_body(), dropdown_font=get_font_body(),
            fg_color=get_color("ROW_BG"), button_color=get_color("ROW_BG"),
            button_hover_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"),
        )
        self.combo.grid(row=0, column=1, rowspan=2, sticky="e", padx=(20, 0))

        # Appearance Mode Selector
        row_mode = ctk.CTkFrame(app_card, fg_color="transparent")
        row_mode.grid(row=2, column=0, padx=24, pady=(0, 20), sticky="ew")
        row_mode.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            row_mode, text="Appearance Mode",
            font=get_font_h3(), text_color=get_color("TEXT_PRIMARY"),
        ).grid(row=0, column=0, sticky="w", pady=4)

        ctk.CTkLabel(
            row_mode, text="Select whether application colors follow the system settings or a fixed preference.",
            font=get_font_body(), text_color=get_color("TEXT_SECONDARY"),
        ).grid(row=1, column=0, sticky="w")

        modes = ["System", "Dark", "Light"]
        self.mode_var = ctk.StringVar(value=TM.get_setting("appearance_mode", "System"))
        self.mode_combo = ctk.CTkOptionMenu(
            row_mode, values=modes, variable=self.mode_var,
            command=self._on_mode_changed,
            font=get_font_body(), dropdown_font=get_font_body(),
            fg_color=get_color("ROW_BG"), button_color=get_color("ROW_BG"),
            button_hover_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"),
        )
        self.mode_combo.grid(row=0, column=1, rowspan=2, sticky="e", padx=(20, 0))

        # Palettes Preview Row (Shows comparison of all 3 themes side-by-side)
        palettes_frame = ctk.CTkFrame(app_card, fg_color="transparent")
        palettes_frame.grid(row=3, column=0, padx=24, pady=(0, 20), sticky="ew")
        palettes_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        theme_previews = [
            ("Midnight Pro", "#050505", "#111111", "#00D4FF", "#00FFB3"),
            ("Dark",         "#0B0F14", "#111827", "#3B82F6", "#22C55E"),
            ("Light",        "#F8FAFC", "#FFFFFF", "#2563EB", "#16A34A")
        ]
        
        for idx, (name, bg, card_bg, accent, success) in enumerate(theme_previews):
            f = ctk.CTkFrame(palettes_frame, fg_color=get_color("ROW_BG"), corner_radius=8, border_width=1, border_color=get_color("BORDER"))
            f.grid(row=0, column=idx, padx=(0 if idx==0 else 6, 0 if idx==2 else 6), sticky="ew")
            
            ctk.CTkLabel(f, text=name, font=get_font_body("bold"), text_color=get_color("TEXT_PRIMARY")).pack(pady=(8, 4))
            
            swatches = ctk.CTkFrame(f, fg_color="transparent")
            swatches.pack(pady=(0, 8))
            
            def make_swatch(parent, color):
                sf = ctk.CTkFrame(parent, width=18, height=18, fg_color=color, corner_radius=9, border_width=1, border_color=get_color("BORDER"))
                sf.pack(side="left", padx=3)
                sf.grid_propagate(False)
            
            make_swatch(swatches, bg)
            make_swatch(swatches, card_bg)
            make_swatch(swatches, accent)
            make_swatch(swatches, success)

        # Live Preview Panel
        preview_frame = ctk.CTkFrame(
            app_card, fg_color=get_color("APP_BG"), corner_radius=8,
            border_width=BORDER_WIDTH, border_color=get_color("BORDER"),
        )
        preview_frame.grid(row=4, column=0, padx=24, pady=(0, 24), sticky="ew")
        preview_frame.grid_columnconfigure(0, weight=1)
        preview_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            preview_frame, text="Live Theme Preview Dashboard",
            font=get_font_body("bold"), text_color=get_color("TEXT_SECONDARY"),
        ).grid(row=0, column=0, columnspan=2, padx=16, pady=(12, 12), sticky="w")

        # Column 0: Miniature Dashboard Card
        mini_card = ctk.CTkFrame(
            preview_frame, fg_color=get_color("CARD_BG"), corner_radius=RADIUS,
            border_width=BORDER_WIDTH, border_color=get_color("BORDER"),
        )
        mini_card.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")
        mini_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            mini_card, text="Sample Finding", font=get_font_h3(),
            text_color=get_color("TEXT_PRIMARY")
        ).pack(anchor="w", padx=16, pady=(12, 2))

        # Severity and Match Quality
        meta_row = ctk.CTkFrame(mini_card, fg_color="transparent")
        meta_row.pack(fill="x", padx=16, pady=2)

        sev_badge = ctk.CTkFrame(meta_row, fg_color=get_color("CRITICAL"), corner_radius=4)
        sev_badge.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(sev_badge, text="CRITICAL", font=get_font_caption("bold"), text_color="#FFFFFF").pack(padx=6, pady=2)

        ctk.CTkLabel(
            meta_row, text="Match Quality: Excellent (95%)", font=get_font_caption("bold"),
            text_color=get_color("SUCCESS")
        ).pack(side="left")

        # Input Preview
        ctk.CTkLabel(
            mini_card, text="Description Preview", font=get_font_caption("bold"),
            text_color=get_color("TEXT_SECONDARY")
        ).pack(anchor="w", padx=16, pady=(8, 2))

        desc_input = ctk.CTkEntry(
            mini_card, placeholder_text="", font=get_font_body(), height=30,
            fg_color=get_color("ROW_BG"), border_color=get_color("BORDER"),
            text_color=get_color("TEXT_PRIMARY"),
        )
        desc_input.insert(0, "Sample vulnerability description")
        desc_input.configure(state="readonly")
        desc_input.pack(fill="x", padx=16, pady=(0, 12))

        # Metrics sub-card inside mini-card
        metrics_box = ctk.CTkFrame(mini_card, fg_color=get_color("ROW_BG"), corner_radius=8)
        metrics_box.pack(fill="x", padx=16, pady=(0, 16))
        metrics_box.grid_columnconfigure((0, 1, 2), weight=1)

        def make_mini_metric(col, val, label, color):
            f = ctk.CTkFrame(metrics_box, fg_color="transparent")
            f.grid(row=0, column=col, pady=8, sticky="ew")
            ctk.CTkLabel(f, text=val, font=get_font_body("bold"), text_color=color).pack()
            ctk.CTkLabel(f, text=label, font=get_font_caption(), text_color=get_color("TEXT_SECONDARY")).pack()

        make_mini_metric(0, "92%", "Compliance", get_color("SUCCESS"))
        make_mini_metric(1, "8", "Findings", get_color("CRITICAL"))
        make_mini_metric(2, "113", "KB Entries", get_color("ACCENT"))

        # Column 1: Live Interactive Controls (Badges & Buttons)
        controls_card = ctk.CTkFrame(preview_frame, fg_color="transparent")
        controls_card.grid(row=1, column=1, padx=16, pady=(0, 16), sticky="nsew")

        # Buttons
        ctk.CTkLabel(controls_card, text="Button States", font=get_font_caption("bold"), text_color=get_color("TEXT_SECONDARY")).pack(anchor="w", pady=(0, 4))

        primary_btn = ctk.CTkButton(
            controls_card, text="Primary Action", height=32, corner_radius=6,
            fg_color=get_color("ACCENT"), hover_color=get_color("BORDER"),
            font=get_font_body("bold"), text_color="#FFFFFF"
        )
        primary_btn.pack(fill="x", pady=4)

        secondary_btn = ctk.CTkButton(
            controls_card, text="Secondary Action", height=32, corner_radius=6,
            fg_color=get_color("ROW_BG"), hover_color=get_color("BORDER"),
            font=get_font_body("bold"), text_color=get_color("TEXT_PRIMARY"),
            border_width=1, border_color=get_color("BORDER")
        )
        secondary_btn.pack(fill="x", pady=(4, 12))

        # Badges list
        ctk.CTkLabel(controls_card, text="Severity Alerts", font=get_font_caption("bold"), text_color=get_color("TEXT_SECONDARY")).pack(anchor="w", pady=(0, 4))

        badges_row = ctk.CTkFrame(controls_card, fg_color="transparent")
        badges_row.pack(fill="x", pady=2)

        def make_alert_badge(parent, text, color):
            f = ctk.CTkFrame(parent, fg_color=get_color("ROW_BG"), corner_radius=6, border_width=1, border_color=get_color("BORDER"))
            f.pack(side="left", padx=4, expand=True, fill="x")
            ctk.CTkLabel(f, text=text, text_color=color, font=get_font_caption("bold")).pack(padx=8, pady=4)

        make_alert_badge(badges_row, "SUCCESS", get_color("SUCCESS"))
        make_alert_badge(badges_row, "WARNING", get_color("WARNING"))
        make_alert_badge(badges_row, "CRITICAL", get_color("CRITICAL"))

        # ── Report Export Location Card ─────────────────────────────────────
        rep_card = ctk.CTkFrame(
            S, fg_color=get_color("CARD_BG"), corner_radius=RADIUS,
            border_width=BORDER_WIDTH, border_color=get_color("BORDER"),
        )
        rep_card.grid(row=3, column=0, padx=32, pady=(0, 24), sticky="ew")
        rep_card.grid_columnconfigure(0, weight=1)

        r_hdr = ctk.CTkFrame(rep_card, fg_color="transparent")
        r_hdr.grid(row=0, column=0, padx=24, pady=(20, 12), sticky="ew")
        r_hdr.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(
            r_hdr, text="Report Export Location",
            font=get_font_h2(), text_color=get_color("TEXT_PRIMARY"),
        ).grid(row=0, column=0, sticky="w")
        
        ctk.CTkLabel(
            r_hdr, text="Choose the default directory where PDF compliance reports will be saved.",
            font=get_font_body(), text_color=get_color("TEXT_SECONDARY"),
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        path_row = ctk.CTkFrame(rep_card, fg_color="transparent")
        path_row.grid(row=1, column=0, padx=24, pady=(0, 20), sticky="ew")
        path_row.grid_columnconfigure(0, weight=1)

        self._lbl_report_path = ctk.CTkLabel(
            path_row, text=get_reports_dir(), font=get_font_body(),
            text_color=get_color("TEXT_PRIMARY"), fg_color=get_color("ROW_BG"),
            corner_radius=6, height=36, anchor="w"
        )
        self._lbl_report_path.grid(row=0, column=0, sticky="ew", padx=(0, 12), ipadx=10)

        ctk.CTkButton(
            path_row, text="Browse...", font=get_font_body("bold"),
            fg_color=get_color("ROW_BG"), hover_color=get_color("BORDER"),
            text_color=get_color("TEXT_PRIMARY"), height=36, width=100,
            command=self._cmd_browse_reports_dir
        ).grid(row=0, column=1)

        # ── Application Data Card ───────────────────────────────────────────
        data_card = ctk.CTkFrame(
            S, fg_color=get_color("CARD_BG"), corner_radius=RADIUS,
            border_width=BORDER_WIDTH, border_color=get_color("BORDER"),
        )
        data_card.grid(row=3, column=0, padx=32, pady=(0, 32), sticky="ew")
        data_card.grid_columnconfigure(0, weight=1)

        # Card header
        d_hdr = ctk.CTkFrame(data_card, fg_color="transparent")
        d_hdr.grid(row=0, column=0, padx=24, pady=(20, 4), sticky="ew")
        d_hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            d_hdr, text="Application Data",
            font=get_font_h2(), text_color=get_color("TEXT_PRIMARY"),
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            d_hdr,
            text="Manage stored platform statistics, scan history, and report index. "
                 "All destructive actions require confirmation.",
            font=get_font_body(), text_color=get_color("TEXT_SECONDARY"),
            wraplength=700, justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        # Stats summary
        self._stats_lbl = ctk.CTkLabel(
            data_card, text="Loading…", font=get_font_caption(),
            text_color=get_color("TEXT_SECONDARY"),
        )
        self._stats_lbl.grid(row=1, column=0, padx=24, pady=(12, 0), sticky="w")

        # Divider
        ctk.CTkFrame(data_card, height=1, fg_color=get_color("BORDER")).grid(
            row=2, column=0, sticky="ew", padx=24, pady=12,
        )

        # Action buttons
        btn_area = ctk.CTkFrame(data_card, fg_color="transparent")
        btn_area.grid(row=3, column=0, padx=24, pady=(0, 24), sticky="ew")
        btn_area.grid_columnconfigure((0, 1, 2), weight=1)

        def action_btn(col, text, desc, color_key, cmd):
            f = ctk.CTkFrame(btn_area, fg_color=get_color("ROW_BG"), corner_radius=8)
            f.grid(row=0, column=col, padx=(0 if col == 0 else 12, 0), sticky="ew")
            ctk.CTkLabel(f, text=text, font=get_font_body("bold"),
                         text_color=get_color("TEXT_PRIMARY")).pack(
                anchor="w", padx=16, pady=(14, 2))
            ctk.CTkLabel(f, text=desc, font=get_font_caption(),
                         text_color=get_color("TEXT_SECONDARY"),
                         wraplength=200, justify="left").pack(
                anchor="w", padx=16)
            ctk.CTkButton(
                f, text=text, height=34, corner_radius=6,
                font=get_font_body("bold"),
                fg_color=get_color(color_key),
                hover_color=get_color("BORDER"),
                text_color=get_color("TEXT_PRIMARY") if color_key != "CRITICAL" else "#FFFFFF",
                command=cmd,
            ).pack(fill="x", padx=16, pady=(10, 14))

        action_btn(0, "Clear Activity History",
                   "Removes the recent activity log from the dashboard.",
                   "ROW_BG", self._cmd_clear_activity)

        action_btn(1, "Reset Dashboard Statistics",
                   "Clears scan history and resets all dashboard KPIs to zero.",
                   "ROW_BG", self._cmd_reset_stats)

        action_btn(2, "Rebuild Report Index",
                   "Re-scans the reports folder to refresh the Reports page listing.",
                   "ACCENT", self._cmd_rebuild_reports)

    # ── Callbacks ───────────────────────────────────────────────────────────

    def on_show(self) -> None:
        self._refresh_stats_summary()

    def _refresh_stats_summary(self):
        rdir = get_reports_dir()
        ddir = get_data_dir()

        # Count scan history entries
        hist_path = os.path.join(ddir, "scan_history.json")
        scans = 0
        if os.path.exists(hist_path):
            try:
                with open(hist_path, "r", encoding="utf-8") as f:
                    scans = len(json.load(f))
            except Exception:
                pass

        # Count activity entries
        act_path = os.path.join(ddir, "activity_log.json")
        activities = 0
        if os.path.exists(act_path):
            try:
                with open(act_path, "r", encoding="utf-8") as f:
                    activities = len(json.load(f))
            except Exception:
                pass

        # Count report files
        reports = 0
        if os.path.exists(rdir):
            reports = sum(1 for f in os.listdir(rdir)
                          if f.endswith((".pdf", ".txt", ".docx")))

        self._stats_lbl.configure(
            text=f"Stored: {scans} scans  •  {activities} activity entries  •  {reports} report files"
        )

    def _cmd_clear_activity(self):
        if not CustomDialog(
            "Clear Activity History",
            "This will permanently delete all recent activity entries.\n"
            "Dashboard activity feed will be empty after clearing.\n\nContinue?",
            "confirm",
        ).show():
            return
        act_path = os.path.join(get_data_dir(), "activity_log.json")
        try:
            if os.path.exists(act_path):
                os.remove(act_path)
            # Also reset in-memory on the dashboard
            dash = self._main_window._pages.get("dashboard")
            if dash:
                dash._activity_log = []
                dash._refresh()
            self._refresh_stats_summary()
            CustomDialog("Done", "Activity history cleared successfully.", "success").show()
        except Exception as exc:
            CustomDialog("Error", f"Could not clear activity log:\n{exc}", "error").show()

    def _cmd_reset_stats(self):
        if not CustomDialog(
            "Reset Dashboard Statistics",
            "This will permanently delete all scan history.\n"
            "Dashboard KPIs will reset to zero.\n\nThis cannot be undone. Continue?",
            "confirm",
        ).show():
            return
        ddir = get_data_dir()
        removed = 0
        for fname in ("scan_history.json", "activity_log.json"):
            path = os.path.join(ddir, fname)
            try:
                if os.path.exists(path):
                    os.remove(path)
                    removed += 1
            except Exception:
                pass
        # Reset dashboard in-memory state
        dash = self._main_window._pages.get("dashboard")
        if dash:
            dash._scan_log = []
            dash._activity_log = []
            dash._refresh()
        self._refresh_stats_summary()
        CustomDialog("Done", f"Dashboard statistics reset. {removed} data file(s) removed.",
                     "success").show()

    def _cmd_rebuild_reports(self):
        rpage = self._main_window._pages.get("reports")
        if rpage:
            rpage._refresh_list()
        self._refresh_stats_summary()
        CustomDialog("Done", "Report index rebuilt from reports folder.", "success").show()

    def _on_theme_changed(self, choice: str):
        TM.set_theme(choice)
        self.mode_var.set(TM.get_setting("appearance_mode", "System"))
        self._main_window.rebuild_ui("settings")

    def _on_mode_changed(self, choice: str):
        TM.set_appearance_mode(choice)
        import customtkinter as ctk
        ctk.set_appearance_mode(choice.lower())
        self.theme_var.set(TM.get_theme_name())
        self._main_window.rebuild_ui("settings")

    def _cmd_browse_reports_dir(self):
        path = filedialog.askdirectory(title="Select Default Report Directory")
        if path:
            TM.set_setting("custom_reports_dir", path)
            self._lbl_report_path.configure(text=get_reports_dir())
            CustomDialog("Saved", "Report export location updated.", "success").show()
