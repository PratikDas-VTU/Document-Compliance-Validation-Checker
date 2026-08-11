"""
scan_page.py — Scan Document page.
Phase 5C: Multi-stage UI, StatusBadges, and CustomDialogs.
"""
from __future__ import annotations
import os
import sys
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from tkinter import filedialog
import customtkinter as ctk

from datetime import datetime
from app.services.scanner import Scanner, ScanResult
from app.services.report_exporter import export_report_to_path
from app.ui.theme import get_color, get_font_h1, get_font_h2, get_font_h3, get_font_body, get_font_caption, RADIUS, BORDER_WIDTH
from app.ui.components import StatusBadge, CustomDialog

VALIDATOR_DEFS = [
    ("required_section_validation", "Required Sections",  True),
    ("date_validation",             "Date Validation",    True),
    ("vulnerability_validation",    "Vulnerability Check",True),
    ("terminology_validation",      "Terminology Check",  True),
    ("spelling_validation",         "Spelling Check",     True),
    ("empty_page_validation",       "Empty Page Check",   True),
    ("serial_number_validation",    "Serial Numbers",     True),
    ("page_number_validation",      "Page Numbers",       False),
    ("branding_validation",         "Branding Check",     True),
]

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 25
        self.tip_window = tw = ctk.CTkToplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        lbl = ctk.CTkLabel(
            tw, text=self.text, justify="left",
            fg_color=get_color("ROW_BG"),
            text_color=get_color("TEXT_PRIMARY"),
            corner_radius=6,
            border_width=1,
            border_color=get_color("BORDER"),
            font=get_font_caption()
        )
        lbl.pack(ipadx=8, ipady=4)

    def hide_tip(self, event=None):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            try:
                tw.destroy()
            except:
                pass

class ScanPage(ctk.CTkFrame):
    def __init__(self, parent, main_window, **kwargs):
        print("Scan Page Created")
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._main_window   = main_window
        self._main_window.active_scan_page = self
        self._scanner       = Scanner()
        self._file_path     = ""
        self._last_result: ScanResult | None = None
        self._export_pool   = ThreadPoolExecutor(max_workers=1, thread_name_prefix="exporter")
        self._validator_vars: dict[str, ctk.BooleanVar] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.grid(row=0, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        def custom_mouse_wheel_all(event):
            if self._scroll.check_if_master_is_canvas(event.widget):
                if hasattr(self, "_discovery_scroll") and self._discovery_scroll.winfo_exists():
                    try:
                        if self._discovery_scroll.check_if_master_is_canvas(event.widget):
                            return
                    except Exception:
                        pass
                if sys.platform == "darwin":
                    self._scroll._parent_canvas.yview_scroll(int(-1 * event.delta * 3), "units")
                else:
                    self._scroll._parent_canvas.yview_scroll(int(-1 * (event.delta / 120) * 3), "units")
        
        def custom_mouse_wheel_all_button(event):
            if self._scroll.check_if_master_is_canvas(event.widget):
                if hasattr(self, "_discovery_scroll") and self._discovery_scroll.winfo_exists():
                    try:
                        if self._discovery_scroll.check_if_master_is_canvas(event.widget):
                            return
                    except Exception:
                        pass
                if event.num == 4:
                    self._scroll._parent_canvas.yview_scroll(-3, "units")
                elif event.num == 5:
                    self._scroll._parent_canvas.yview_scroll(3, "units")

        self._scroll._mouse_wheel_all = custom_mouse_wheel_all
        if sys.platform.startswith("linux"):
            self._scroll._mouse_wheel_all_button = custom_mouse_wheel_all_button

        self._build()

    def _build(self) -> None:
        S = self._scroll

        # Page header
        ctk.CTkLabel(
            S, text="Scan Center", font=get_font_h1(), text_color=get_color("TEXT_PRIMARY"),
        ).grid(row=0, column=0, padx=32, pady=(28, 4), sticky="w")

        ctk.CTkLabel(
            S, text="Upload a PDF or DOCX file to execute the compliance validation engine.",
            font=get_font_body(), text_color=get_color("TEXT_SECONDARY"),
        ).grid(row=1, column=0, padx=32, pady=(0, 24), sticky="w")

        # ── Upload & Modules (Two-Column Layout) ─────────────────────────────
        top_grid = ctk.CTkFrame(S, fg_color="transparent")
        top_grid.grid(row=2, column=0, padx=32, pady=(0, 24), sticky="ew")
        top_grid.grid_columnconfigure(0, weight=35)
        top_grid.grid_columnconfigure(1, weight=65)

        # Left Column: Document Selection Card
        doc_card = ctk.CTkFrame(top_grid, fg_color=get_color("CARD_BG"), corner_radius=12, border_width=1, border_color=get_color("BORDER"))
        doc_card.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        doc_card.grid_columnconfigure(0, weight=1)

        hdr_left = ctk.CTkFrame(doc_card, fg_color="transparent")
        hdr_left.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))
        hdr_left.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr_left, text="Document Selection", font=get_font_h3(), text_color=get_color("TEXT_PRIMARY")).grid(row=0, column=0, sticky="w")
        self._status_badge = StatusBadge(hdr_left, state="Ready")
        self._status_badge.grid(row=0, column=1, sticky="e")

        self._drop_zone = ctk.CTkFrame(doc_card, fg_color=get_color("APP_BG"), corner_radius=8, border_width=1, border_color=get_color("BORDER"))
        self._drop_zone.grid(row=1, column=0, padx=20, pady=(0, 16), sticky="ew")
        self._drop_zone.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self._drop_zone, text="📄", font=ctk.CTkFont(size=36)).grid(row=0, column=0, pady=(20, 4))
        self._file_label = ctk.CTkLabel(self._drop_zone, text="Browse PDF or DOCX", font=get_font_body("bold"), text_color=get_color("TEXT_PRIMARY"))
        self._file_label.grid(row=1, column=0, pady=(0, 4))
        self._file_size_label = ctk.CTkLabel(self._drop_zone, text="No document selected", font=get_font_caption(), text_color=get_color("TEXT_MUTED"))
        self._file_size_label.grid(row=2, column=0, pady=(0, 20))

        # Action Buttons inside Doc Card
        btn_frame = ctk.CTkFrame(doc_card, fg_color="transparent")
        btn_frame.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkButton(
            btn_frame, text="Browse", height=36, corner_radius=8,
            fg_color=get_color("BORDER"), hover_color=get_color("ROW_BG"), text_color=get_color("TEXT_PRIMARY"), font=get_font_body("bold"),
            command=self._browse_file
        ).grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self._scan_btn = ctk.CTkButton(
            btn_frame, text="▶ Start Scan", height=36, corner_radius=8,
            fg_color=get_color("ACCENT"), hover_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"), font=get_font_body("bold"),
            command=self._start_scan
        )
        self._scan_btn.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        self._cancel_btn = ctk.CTkButton(
            btn_frame, text="✕ Cancel", height=36, corner_radius=8,
            fg_color=get_color("CRITICAL"), hover_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"), font=get_font_body("bold"),
            command=self._cancel_scan, state="disabled"
        )
        self._cancel_btn.grid(row=1, column=0, columnspan=2, pady=(8, 0), sticky="ew")
        self._cancel_btn.grid_remove() # hide by default

        # Right Column: Active Modules Card
        mod_card = ctk.CTkFrame(top_grid, fg_color=get_color("CARD_BG"), corner_radius=12, border_width=1, border_color=get_color("BORDER"))
        mod_card.grid(row=0, column=1, sticky="nsew", padx=(16, 0))
        mod_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(mod_card, text="Active Modules", font=get_font_h3(), text_color=get_color("TEXT_PRIMARY")).grid(row=0, column=0, padx=20, pady=(16, 12), sticky="w")

        mod_grid = ctk.CTkFrame(mod_card, fg_color="transparent")
        mod_grid.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        mod_grid.grid_columnconfigure((0, 1), weight=1)

        for idx, (key, label, default) in enumerate(VALIDATOR_DEFS):
            var = ctk.BooleanVar(value=default)
            self._validator_vars[key] = var
            
            # Module Card
            mc = ctk.CTkFrame(mod_grid, fg_color=get_color("APP_BG"), corner_radius=8, border_width=1, border_color=get_color("BORDER"))
            mc.grid(row=idx // 2, column=idx % 2, padx=6, pady=6, sticky="ew")
            mc.grid_columnconfigure(0, weight=1)
            
            icon = "🛡️" if "Validation" in label or "Check" in label else "⚙️"
            title_frame = ctk.CTkFrame(mc, fg_color="transparent")
            title_frame.pack(fill="x", padx=12, pady=(12, 4))
            ctk.CTkLabel(title_frame, text=f"{icon} {label}", font=get_font_body("bold"), text_color=get_color("TEXT_PRIMARY")).pack(side="left")
            
            sw = ctk.CTkSwitch(title_frame, text="", variable=var, width=40, progress_color=get_color("ACCENT"))
            sw.pack(side="right")
            
            desc = "Security rules compliance." if "Vulnerability" in label else "General structure formatting."
            ctk.CTkLabel(mc, text=desc, font=get_font_caption(), text_color=get_color("TEXT_MUTED")).pack(side="left", padx=12, pady=(0, 12))

        # ── Progress section (Timeline Style) ─────────────────────────────────
        self._progress_card = ctk.CTkFrame(S, fg_color=get_color("CARD_BG"), corner_radius=12, border_width=1, border_color=get_color("BORDER"))
        self._progress_card.grid(row=3, column=0, padx=32, pady=(0, 24), sticky="ew")
        self._progress_card.grid_columnconfigure(0, weight=1)
        self._progress_card.grid_remove()

        stages = [
            ("parsing", "Parsing"),
            ("rules", "Loading Rules"),
            ("validating", "Validating"),
            ("calculating", "Calculating"),
            ("generating", "Generating Report")
        ]
        
        stages_frame = ctk.CTkFrame(self._progress_card, fg_color="transparent")
        stages_frame.grid(row=0, column=0, padx=24, pady=16, sticky="ew")
        for i in range(len(stages)):
            stages_frame.grid_columnconfigure(i, weight=1)
        
        self._stage_labels = {}
        for idx, (key, text) in enumerate(stages):
            f = ctk.CTkFrame(stages_frame, fg_color="transparent")
            f.grid(row=0, column=idx, sticky="ew")
            
            pill = ctk.CTkFrame(f, fg_color="transparent", corner_radius=16, border_width=1, border_color=get_color("BORDER"))
            pill.pack(anchor="center", pady=4, padx=4)
            
            icon_lbl = ctk.CTkLabel(pill, text="○", font=get_font_body("bold"), text_color=get_color("TEXT_SECONDARY"))
            icon_lbl.pack(side="left", padx=(12, 4), pady=6)
            
            text_lbl = ctk.CTkLabel(pill, text=text, font=get_font_body("bold"), text_color=get_color("TEXT_SECONDARY"))
            text_lbl.pack(side="left", padx=(0, 12), pady=6)
            
            self._stage_labels[key] = {
                "pill": pill,
                "icon": icon_lbl,
                "text": text_lbl
            }

        # ── Results section ───────────────────────────────────────────────────
        self._transition_banner = ctk.CTkFrame(S, fg_color="transparent")
        self._transition_banner.grid(row=5, column=0, pady=(24, 0))
        ctk.CTkLabel(self._transition_banner, text="✓ Scan Complete", font=get_font_h2(), text_color=get_color("SUCCESS")).pack()
        self._transition_banner.grid_remove()

        self._results_container = ctk.CTkFrame(S, fg_color="transparent")
        self._results_container.grid(row=6, column=0, padx=32, pady=(16, 48), sticky="ew")
        self._results_container.grid_columnconfigure(0, weight=3, uniform="results")
        self._results_container.grid_columnconfigure(1, weight=1, uniform="results", minsize=320)
        self._results_container.grid_remove()

        self._results_card = ctk.CTkFrame(self._results_container, fg_color=get_color("ROW_BG"), corner_radius=12, border_width=1, border_color=get_color("BORDER"))
        self._results_card.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        self._results_card.grid_columnconfigure(0, weight=1)

        self._discovery_panel = ctk.CTkFrame(self._results_container, fg_color="transparent")
        self._discovery_panel.grid(row=0, column=1, sticky="nsew")
        self._discovery_panel.grid_columnconfigure(0, weight=1)
        
        # Fixed layout: 83% report, 17% discovery sidebar
        # No dynamic resize to avoid Configure race condition with grid_remove/grid

        self._build_results_area()

    def _enable_word_wrap(self, label: ctk.CTkLabel, padding: int = 32):
        """Dynamically adjusts the wraplength of a CTkLabel based on self._discovery_card's width."""
        def on_configure(event):
            try:
                if not hasattr(self, "_discovery_card") or not self._discovery_card.winfo_exists():
                    return
                w = self._discovery_card.winfo_width()
                if w > 1:
                    target_wrap = max(50, w - padding)
                    if getattr(label, "_last_wrap", None) != target_wrap:
                        label._last_wrap = target_wrap
                        label.configure(wraplength=target_wrap)
            except Exception:
                pass

        self._discovery_card.bind("<Configure>", on_configure, add="+")
        
        # Initialize immediately if possible
        try:
            if hasattr(self, "_discovery_card") and self._discovery_card.winfo_exists():
                w = self._discovery_card.winfo_width()
                if w > 1:
                    target_wrap = max(50, w - padding)
                    label._last_wrap = target_wrap
                    label.configure(wraplength=target_wrap)
        except Exception:
            pass

    def _build_section_container(self, parent, title, accent_color, top_pad=0, subtitle=None):
        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.grid(column=0, sticky="ew", padx=32, pady=(top_pad, 8))
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text=title, font=get_font_h3(), text_color=get_color("TEXT_PRIMARY")).pack(side="left")
        if subtitle:
            ctk.CTkLabel(hdr, text=subtitle, font=get_font_caption(), text_color=get_color("TEXT_MUTED")).pack(side="left", padx=(12, 0), pady=(2, 0))
        
        outer = ctk.CTkFrame(parent, fg_color=accent_color, corner_radius=8)
        outer.grid(column=0, sticky="ew", padx=32, pady=(0, 24))
        outer.grid_columnconfigure(0, weight=1)
        
        inner = ctk.CTkFrame(outer, fg_color=get_color("CARD_BG"), corner_radius=6)
        inner.grid(row=0, column=0, sticky="nsew", padx=(4, 0))
        inner.grid_columnconfigure((0, 1, 2, 3), weight=1)
        return inner

    def _build_results_area(self):
        # 1. Report Header
        hdr_frame = ctk.CTkFrame(self._results_card, fg_color="transparent")
        hdr_frame.grid(row=0, column=0, sticky="ew", padx=32, pady=(32, 24))
        hdr_frame.grid_columnconfigure(0, weight=1)
        
        title_box = ctk.CTkFrame(hdr_frame, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(title_box, text="Compliance Report", font=get_font_h1(), text_color=get_color("TEXT_PRIMARY")).pack(anchor="w")
        ctk.CTkLabel(title_box, text="Comprehensive analysis of document compliance and security posture.", font=get_font_caption(), text_color=get_color("TEXT_MUTED")).pack(anchor="w", pady=(4,0))
        
        acts = ctk.CTkFrame(hdr_frame, fg_color="transparent")
        acts.grid(row=0, column=1, sticky="e")
        self._btn_export = ctk.CTkButton(acts, text="📄 Export", width=100, height=32, fg_color=get_color("ACCENT"), hover_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"), font=get_font_body("bold"), command=self._export_report)
        self._btn_export.pack(side="left", padx=(0, 8))
        self._btn_open_report = ctk.CTkButton(acts, text="👁 Open", width=100, height=32, fg_color=get_color("BORDER"), hover_color=get_color("ROW_BG"), text_color=get_color("TEXT_PRIMARY"), font=get_font_body("bold"), command=self._open_exported_report)
        self._btn_open_report.pack(side="left")

        # 2. Scanned Details Banner
        self._details_card = self._build_section_container(self._results_card, "Scanned Details", get_color("ACCENT"))
        
        # 3. Executive Summary
        self._exec_card = self._build_section_container(self._results_card, "Executive Summary", get_color("BORDER"), top_pad=12)
        
        def make_stat(parent, col, title, color=get_color("TEXT_PRIMARY")):
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.grid(row=0, column=col, padx=16, pady=16, sticky="ew")
            v = ctk.CTkLabel(f, text="0", font=get_font_h1(), text_color=color)
            v.pack(anchor="w")
            ctk.CTkLabel(f, text=title, font=get_font_caption(), text_color=get_color("TEXT_MUTED")).pack(anchor="w", pady=(4, 0))
            return v
            
        self._exec_card.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=1)
        self._lbl_score    = make_stat(self._exec_card, 0, "Score", get_color("ACCENT"))
        self._lbl_grade    = make_stat(self._exec_card, 1, "Status", get_color("TEXT_PRIMARY"))
        self._lbl_critical = make_stat(self._exec_card, 2, "Critical", get_color("CRITICAL"))
        self._lbl_warning  = make_stat(self._exec_card, 3, "Warning", get_color("WARNING"))
        self._lbl_info     = make_stat(self._exec_card, 4, "Info", get_color("ACCENT"))
        self._lbl_passed   = make_stat(self._exec_card, 5, "Passed", get_color("SUCCESS"))

        # 4. Branding Validation Summary
        self._branding_card = self._build_section_container(self._results_card, "Branding Validation Summary", get_color("SUCCESS"), top_pad=12)
        
        # 5. Vulnerability Intelligence Summary
        self._vuln_card = self._build_section_container(self._results_card, "Vulnerability Intelligence Summary", "#8B5CF6", top_pad=12)
        
        # 6. Compliance Validation Summary
        self._comp_card = self._build_section_container(self._results_card, "Compliance Validation Summary", get_color("ACCENT"), top_pad=12)

        # 7. Detailed Findings
        self._findings_outer = ctk.CTkFrame(self._results_card, fg_color=get_color("WARNING"), corner_radius=8)
        self._findings_outer.grid(column=0, sticky="ew", padx=32, pady=(12, 24))
        self._findings_outer.grid_columnconfigure(0, weight=1)
        
        inner_f = ctk.CTkFrame(self._findings_outer, fg_color=get_color("APP_BG"), corner_radius=6)
        inner_f.grid(row=0, column=0, sticky="nsew", padx=(4, 0))
        inner_f.grid_columnconfigure(0, weight=1)
        
        hdr = ctk.CTkFrame(inner_f, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 16))
        ctk.CTkLabel(hdr, text="Detailed Findings", font=get_font_h3(), text_color=get_color("TEXT_PRIMARY")).pack(side="left")
        ctk.CTkLabel(hdr, text="Click a finding to view detailed analysis, evidence, and intelligence insights.", font=get_font_caption(), text_color=get_color("TEXT_MUTED")).pack(side="left", padx=(12, 0), pady=(2, 0))
        
        # Replace ScrollableFrame with simple Frame since page scrolls
        self._findings_frame = ctk.CTkFrame(inner_f, fg_color="transparent")
        self._findings_frame.grid(row=1, column=0, padx=16, pady=(0, 24), sticky="nsew")
        self._findings_frame.grid_columnconfigure(0, weight=1)
        
        # 8. Recommendations
        self._rec_card = self._build_section_container(self._results_card, "Recommendations", get_color("SUCCESS"), top_pad=12)
        self._rec_card.grid_columnconfigure(0, weight=1)

        # 9. Knowledge Discovery Review
        # 9. Knowledge Discovery Review
        self._discovery_card = self._build_section_container(self._discovery_panel, "Knowledge Discovery", get_color("ACCENT"), top_pad=0, subtitle="Learning Queue")
        
        # Summary block at the top
        sum_f = ctk.CTkFrame(self._discovery_card, fg_color="transparent")
        sum_f.pack(fill="x", padx=16, pady=(12, 4))
        sum_f.grid_columnconfigure((0, 1), weight=1)
        
        def make_sum_lbl(parent, r, text):
            lbl = ctk.CTkLabel(parent, text=text, font=get_font_caption(), text_color=get_color("TEXT_MUTED"))
            lbl.grid(row=r, column=0, sticky="w", pady=1)
            self._enable_word_wrap(lbl, padding=160)
            v = ctk.CTkLabel(parent, text="-", font=get_font_caption("bold"), text_color=get_color("TEXT_PRIMARY"))
            v.grid(row=r, column=1, sticky="e", pady=1)
            self._enable_word_wrap(v, padding=240)
            return v
            
        self._val_cand_found = make_sum_lbl(sum_f, 0, "Candidates Found:")
        self._val_cand_filtered = make_sum_lbl(sum_f, 1, "Filtered:")
        self._val_cand_eligible = make_sum_lbl(sum_f, 2, "Eligible:")
        self._val_cand_selected = make_sum_lbl(sum_f, 3, "Selected:")
        self._val_cand_updated = make_sum_lbl(sum_f, 4, "Last Updated:")
        
        # Divider line
        div = ctk.CTkFrame(self._discovery_card, fg_color=get_color("BORDER"), height=1)
        div.pack(fill="x", padx=16, pady=8)
        
        # Workflow Status label
        stat_f = ctk.CTkFrame(self._discovery_card, fg_color="transparent")
        stat_f.pack(fill="x", padx=16, pady=(4, 8))
        
        lbl_status_title = ctk.CTkLabel(stat_f, text="Knowledge Discovery Status", font=get_font_caption("bold"), text_color=get_color("TEXT_MUTED"))
        lbl_status_title.pack(anchor="w")
        self._enable_word_wrap(lbl_status_title, padding=48)
        self._lbl_discovery_status = ctk.CTkLabel(stat_f, text="Ready for Review", font=get_font_body("bold"), text_color=get_color("ACCENT"))
        self._lbl_discovery_status.pack(anchor="w")
        self._enable_word_wrap(self._lbl_discovery_status, padding=48)
        
        # Scrollable Frame for candidates (Priority 9)
        self._discovery_scroll = ctk.CTkScrollableFrame(self._discovery_card, fg_color="transparent", height=420)
        self._discovery_scroll.pack(fill="both", expand=True, padx=16, pady=4)
        self._discovery_scroll.grid_columnconfigure(0, weight=1)
        
        # Prevent scroll trap (propagate scroll up/down when at boundaries)
        def discovery_mouse_wheel_all(event):
            if self._discovery_scroll.check_if_master_is_canvas(event.widget):
                canvas_child = self._discovery_scroll._parent_canvas
                canvas_parent = self._scroll._parent_canvas
                top, bottom = canvas_child.yview()
                
                is_scrolling_up = event.delta > 0
                is_scrolling_down = event.delta < 0
                
                if (is_scrolling_up and top <= 0.0) or (is_scrolling_down and bottom >= 1.0):
                    if sys.platform == "darwin":
                        canvas_parent.yview_scroll(int(-1 * event.delta * 3), "units")
                    else:
                        canvas_parent.yview_scroll(int(-1 * (event.delta / 120) * 3), "units")
                else:
                    if sys.platform == "darwin":
                        canvas_child.yview_scroll(int(-1 * event.delta * 3), "units")
                    else:
                        canvas_child.yview_scroll(int(-1 * (event.delta / 120) * 3), "units")
        
        def discovery_mouse_wheel_all_button(event):
            if self._discovery_scroll.check_if_master_is_canvas(event.widget):
                canvas_child = self._discovery_scroll._parent_canvas
                canvas_parent = self._scroll._parent_canvas
                top, bottom = canvas_child.yview()
                
                is_scrolling_up = event.num == 4
                is_scrolling_down = event.num == 5
                
                if (is_scrolling_up and top <= 0.0) or (is_scrolling_down and bottom >= 1.0):
                    if event.num == 4:
                        canvas_parent.yview_scroll(-3, "units")
                    elif event.num == 5:
                        canvas_parent.yview_scroll(3, "units")
                else:
                    if event.num == 4:
                        canvas_child.yview_scroll(-3, "units")
                    elif event.num == 5:
                        canvas_child.yview_scroll(3, "units")

        self._discovery_scroll._mouse_wheel_all = discovery_mouse_wheel_all
        if sys.platform.startswith("linux"):
            self._discovery_scroll._mouse_wheel_all_button = discovery_mouse_wheel_all_button
            
        # Bottom controls container
        btn_box = ctk.CTkFrame(self._discovery_card, fg_color="transparent")
        btn_box.pack(fill="x", padx=16, pady=16)
        
        self._lbl_selected_counter = ctk.CTkLabel(btn_box, text="Selected: 0", font=get_font_body("bold"), text_color=get_color("TEXT_SECONDARY"))
        self._lbl_selected_counter.pack(anchor="w", pady=(0, 8))
        self._enable_word_wrap(self._lbl_selected_counter, padding=48)
        
        self._btn_submit_discovery = ctk.CTkButton(
            btn_box, text="Add to Learning Queue", fg_color=get_color("ACCENT"), hover_color=get_color("BORDER"),
            text_color=get_color("TEXT_PRIMARY"), font=get_font_body("bold"),
            command=self._submit_learning_queue
        )
        self._btn_submit_discovery.pack(fill="x")

    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Document",
            filetypes=[("Documents", "*.pdf *.docx")]
        )
        if path:
            self._file_path = path
            self._file_label.configure(text=os.path.basename(path), text_color=get_color("TEXT_PRIMARY"))
            size_kb = os.path.getsize(path) / 1024
            self._file_size_label.configure(text=f"{size_kb:.1f} KB")
            self._results_container.grid_remove()
            self._status_badge.set_state("Ready")

    def _start_scan(self) -> None:
        if not self._file_path or not os.path.exists(self._file_path):
            CustomDialog("Error", "Please select a valid document first.", "error").show()
            return

        enabled = {k: True for k, v in self._validator_vars.items() if v.get()}
        if not enabled:
            CustomDialog("Warning", "Please enable at least one validation module.", "warning").show()
            return

        self._status_badge.set_state("Scanning")
        self._scan_btn.configure(state="disabled")
        self._cancel_btn.configure(state="normal")
        self._progress_card.grid()
        self._results_container.grid_remove()
        
        # Reset checklist
        for key, stage_ui in self._stage_labels.items():
            stage_ui["pill"].configure(fg_color="transparent", border_color=get_color("BORDER"))
            stage_ui["icon"].configure(text="○", text_color=get_color("TEXT_SECONDARY"))
            stage_ui["text"].configure(text_color=get_color("TEXT_SECONDARY"))

        def _update_progress_safe(pct: float, msg: str) -> None:
            if self.winfo_exists():
                self._update_progress(pct, msg)

        def _scan_finished_safe(res: ScanResult | Exception) -> None:
            if self.winfo_exists():
                self._scan_finished(res)

        def on_prog(pct: float, msg: str):
            try:
                self._main_window.after(0, lambda: _update_progress_safe(pct, msg))
            except Exception:
                pass

        def on_done(res: ScanResult | Exception):
            try:
                self._main_window.after(0, lambda: _scan_finished_safe(res))
            except Exception:
                pass

        self._scanner.start_scan(
            filepath=self._file_path,
            enabled_validators=enabled,
            on_progress=on_prog,
            on_complete=on_done,
            on_error=lambda err: on_done(Exception(err))
        )

    def _update_progress(self, pct: float, msg: str) -> None:
        self._last_progress_pct = pct
        # Map pct to checklist visual
        stages = ["parsing", "rules", "validating", "calculating", "generating"]
        current_idx = 0
        if pct > 0.1: current_idx = 1
        if pct > 0.3: current_idx = 2
        if pct > 0.8: current_idx = 3
        if pct > 0.9: current_idx = 4
        if pct == 1.0: current_idx = 5

        for i, key in enumerate(stages):
            stage_ui = self._stage_labels[key]
            
            if i < current_idx:
                stage_ui["pill"].configure(fg_color="transparent", border_color=get_color("SUCCESS"))
                stage_ui["icon"].configure(text="✓", text_color=get_color("SUCCESS"))
                stage_ui["text"].configure(text_color=get_color("TEXT_PRIMARY"))
            elif i == current_idx:
                stage_ui["pill"].configure(fg_color=get_color("ROW_BG"), border_color=get_color("ACCENT"))
                stage_ui["icon"].configure(text="●", text_color=get_color("ACCENT"))
                stage_ui["text"].configure(text_color=get_color("TEXT_PRIMARY"))
            else:
                stage_ui["pill"].configure(fg_color="transparent", border_color=get_color("BORDER"))
                stage_ui["icon"].configure(text="○", text_color=get_color("TEXT_SECONDARY"))
                stage_ui["text"].configure(text_color=get_color("TEXT_SECONDARY"))

    def _cancel_scan(self) -> None:
        self._scanner.cancel()
        self._cancel_btn.configure(state="disabled")
        self._status_badge.set_state("Failed")

    def _log_debug(self, msg: str) -> None:
        try:
            from app.utils.path_helper import get_logs_path
            log_path = get_logs_path("debug.log")
        except Exception:
            log_path = "debug.log"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_line = f"[{timestamp}] {msg}\n"
        print(log_line.strip())
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception as e:
            print(f"Failed to write to debug log file: {e}")

    def _boost_scroll(self, widget) -> None:
        canvas = self._scroll._parent_canvas
        
        def _on_mousewheel(event):
            if sys.platform == "darwin":
                canvas.yview_scroll(int(-1 * event.delta * 3), "units")
            else:
                canvas.yview_scroll(int(-1 * (event.delta / 120) * 3), "units")
        
        def _on_mousewheel_linux(event):
            if event.num == 4:
                canvas.yview_scroll(-3, "units")
            elif event.num == 5:
                canvas.yview_scroll(3, "units")

        def _bind_recursive(w):
            if sys.platform.startswith("linux"):
                w.bind("<Button-4>", _on_mousewheel_linux, add="+")
                w.bind("<Button-5>", _on_mousewheel_linux, add="+")
            else:
                w.bind("<MouseWheel>", _on_mousewheel, add="+")
            
            for child in w.winfo_children():
                _bind_recursive(child)
                
        _bind_recursive(widget)

    def _scan_finished(self, result: ScanResult | Exception) -> None:
        try:
            self._log_debug("--- Entering _scan_finished ---")
            self._scan_btn.configure(state="normal")
            self._cancel_btn.configure(state="disabled")

            if isinstance(result, Exception):
                self._log_debug(f"Scan finished with exception: {result}")
                self._progress_card.grid_remove()
                self._status_badge.set_state("Failed")
                if str(result) != "Cancelled by user":
                    CustomDialog("Scan Failed", str(result), "error").show()
                return

            self._log_debug("Scan completed successfully. Processing ScanResult...")
            self._last_result = result
            self._status_badge.set_state("Compliant" if result.score == 100 else "Warning")
            self._update_progress(1.0, "")

            self._log_debug(f"Scan score: {result.score}, grade: {result.grade}, critical_count: {result.critical_count}, warning_count: {result.warning_count}, info_count: {result.info_count}")

            dash = self._main_window._pages.get("dashboard")
            if dash:
                self._log_debug("Saving scan data to dashboard...")
                intel_findings = [f for f in result.findings if getattr(f, "confidence_score", 0) > 0]
                avg_mq = sum(f.confidence_score for f in intel_findings) / len(intel_findings) if intel_findings else 0
                
                dash.save_scan(
                    filename=os.path.basename(result.filename), score=result.score, grade=result.grade,
                    critical=result.critical_count,
                    warning=result.warning_count,
                    info=result.info_count,
                    avg_match_quality=avg_mq,
                    discovery_summary=getattr(result, "discovery_summary", {})
                )
                self._log_debug("Dashboard updated successfully.")

            self._log_debug("Calling _populate_results(result)...")
            self._populate_results(result)
            self._log_debug("_populate_results(result) finished successfully.")

            self._log_debug("Mapping result UI components via grid...")
            self._transition_banner.grid(row=5, column=0, pady=(24, 0))
            self._log_debug("_transition_banner.grid called.")
            
            self._results_container.grid(row=6, column=0, padx=32, pady=(16, 48), sticky="ew")
            self._log_debug("_results_container.grid called.")
            
            self._log_debug(f"Before update_idletasks - _results_container winfo_ismapped: {self._results_container.winfo_ismapped()}")
            self._log_debug(f"Before update_idletasks - _results_container size: {self._results_container.winfo_width()}x{self._results_container.winfo_height()}")

            if hasattr(self, "_btn_open_report"):
                self._btn_open_report.pack_forget()

            def _do_scroll():
                try:
                    self._log_debug("Executing _do_scroll callback...")
                    self.update_idletasks()
                    canvas = self._scroll._parent_canvas
                    canvas.configure(scrollregion=canvas.bbox("all"))
                    
                    y_offset = self._transition_banner.winfo_y()
                    bbox = canvas.bbox("all")
                    total_height = bbox[3] if bbox else 0
                    self._log_debug(f"ScrollRegion bbox: {bbox}, total_height: {total_height}, y_offset of transition banner: {y_offset}")
                    self._log_debug(f"After update_idletasks - _results_container winfo_ismapped: {self._results_container.winfo_ismapped()}")
                    self._log_debug(f"After update_idletasks - _results_container size: {self._results_container.winfo_width()}x{self._results_container.winfo_height()}")
                    self._log_debug(f"After update_idletasks - _results_card winfo_ismapped: {self._results_card.winfo_ismapped()} size: {self._results_card.winfo_width()}x{self._results_card.winfo_height()}")
                    self._log_debug(f"After update_idletasks - _discovery_panel winfo_ismapped: {self._discovery_panel.winfo_ismapped()} size: {self._discovery_panel.winfo_width()}x{self._discovery_panel.winfo_height()}")
                    
                    if bbox:
                        if total_height > 0:
                            target_y = max(0, (y_offset - 20) / total_height)
                            self._log_debug(f"Scrolling to target fraction: {target_y}")
                            canvas.yview_moveto(target_y)
                except Exception as ex_scroll:
                    import traceback
                    self._log_debug(f"Exception inside _do_scroll: {ex_scroll}\n{traceback.format_exc()}")

            self.after(100, _do_scroll)
            self._log_debug("--- _scan_finished completed successfully ---")

        except Exception as e:
            import traceback
            self._log_debug(f"FATAL Exception in _scan_finished: {e}\n{traceback.format_exc()}")
            raise

    def _update_card_visuals(self, card, var):
        if var.get():
            card.configure(fg_color=get_color("ROW_BG"))
        else:
            card.configure(fg_color=get_color("APP_BG"))

    def _update_selected_count(self) -> None:
        selected_count = sum(1 for var, cand, frame in self._candidate_vars.values() if var.get())
        if hasattr(self, "_val_cand_selected"):
            self._val_cand_selected.configure(text=str(selected_count))
        if hasattr(self, "_lbl_selected_counter"):
            self._lbl_selected_counter.configure(text=f"Selected: {selected_count}")
        
        # Update workflow status label
        if hasattr(self, "_lbl_discovery_status"):
            if selected_count == 0:
                self._lbl_discovery_status.configure(text="Ready for Review", text_color=get_color("ACCENT"))
            else:
                self._lbl_discovery_status.configure(text=f"{selected_count} Candidates Selected", text_color=get_color("SUCCESS"))

    def _populate_results(self, result: ScanResult) -> None:
        self._log_debug("Entering _populate_results")
        c_crit = result.critical_count
        c_warn = result.warning_count
        c_info = result.info_count
        c_pass = result.passed_checks

        self._lbl_score.configure(text=f"{result.score:.1f}%")
        self._lbl_grade.configure(text=result.grade)
        
        grade_color = get_color("SUCCESS")
        if result.grade == "Non-Compliant": grade_color = get_color("CRITICAL")
        elif result.grade == "Partially Compliant": grade_color = get_color("WARNING")
            
        self._lbl_grade.configure(text_color=grade_color)
        self._lbl_critical.configure(text=str(c_crit))
        self._lbl_warning.configure(text=str(c_warn))
        self._lbl_info.configure(text=str(c_info))
        self._lbl_passed.configure(text=str(c_pass))

        def add_summary_row(parent, row, col, label, value, color=get_color("TEXT_PRIMARY")):
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.grid(row=row, column=col, sticky="ew", padx=16, pady=12)
            ctk.CTkLabel(f, text=label, font=get_font_caption("bold"), text_color=get_color("TEXT_SECONDARY")).pack(anchor="w")
            ctk.CTkLabel(f, text=value, font=get_font_body(), text_color=color).pack(anchor="w", pady=(2, 0))

        # Clear summaries
        self._log_debug("Clearing existing report card and discovery widgets")
        for w in self._details_card.winfo_children(): w.destroy()
        for w in self._branding_card.winfo_children(): w.destroy()
        for w in self._vuln_card.winfo_children(): w.destroy()
        for w in self._comp_card.winfo_children(): w.destroy()
        for w in self._rec_card.winfo_children(): w.destroy()

        # Scanned Details Summary
        self._log_debug("Populating report workspace cards (Details, Branding, Vulnerabilities, Compliance)")
        try:
            sz_kb = os.path.getsize(result.filename) / 1024
            size_str = f"{sz_kb:.1f} KB"
        except:
            size_str = "Unknown"
            
        add_summary_row(self._details_card, 0, 0, "File Name", os.path.basename(result.filename))
        add_summary_row(self._details_card, 0, 1, "File Type", result.file_type.upper())
        add_summary_row(self._details_card, 0, 2, "File Size", size_str)
        add_summary_row(self._details_card, 1, 0, "Page Count", str(result.page_count))
        add_summary_row(self._details_card, 1, 1, "Scan Date", datetime.now().strftime("%Y-%m-%d %H:%M"))
        add_summary_row(self._details_card, 1, 2, "Scan ID", f"SCAN-{hash(result.filename + str(datetime.now().timestamp())) % 1000000:06d}")

        # Branding Summary
        bs = getattr(result, "branding_summary", {})
        add_summary_row(self._branding_card, 0, 0, "Primary Organization", bs.get("primary_org", "Unknown"))
        add_summary_row(self._branding_card, 0, 1, "Logo Present", "Yes" if bs.get("logo_present") else "No")
        add_summary_row(self._branding_card, 0, 2, "Total Logos Detected", str(bs.get("total_logos", 0)))
        
        orgs_str = ", ".join(bs.get("detected_orgs", [])) if bs.get("detected_orgs") else "None"
        add_summary_row(self._branding_card, 0, 3, "Detected Organizations", orgs_str)

        b_stat = bs.get("status", "N/A")
        b_col = get_color("SUCCESS") if b_stat == "Pass" else get_color("CRITICAL") if b_stat == "Failed" else get_color("TEXT_PRIMARY")
        add_summary_row(self._branding_card, 1, 0, "Brand Consistency", bs.get("brand_consistency", "N/A"))
        add_summary_row(self._branding_card, 1, 1, "Consistency Score", f"{bs.get('consistency_score', 0):.1f}%")
        add_summary_row(self._branding_card, 1, 2, "Pages With Logos", str(bs.get("pages_containing_logos", 0)))
        add_summary_row(self._branding_card, 1, 3, "Validation Status", b_stat, b_col)

        # Vulnerability Summary
        vs = getattr(result, "vuln_summary", {})
        add_summary_row(self._vuln_card, 0, 0, "Total Vulnerabilities", str(vs.get("total", 0)))
        add_summary_row(self._vuln_card, 0, 1, "Matched Vulnerabilities", str(vs.get("matched", 0)))
        add_summary_row(self._vuln_card, 0, 2, "Unmatched Vulnerabilities", str(vs.get("unmatched", 0)))
        add_summary_row(self._vuln_card, 0, 3, "Coverage %", f"{vs.get('coverage', 0):.1f}%")

        sev_b = vs.get("severity_breakdown", {})
        sev_str = f"Crit: {sev_b.get('Critical',0)} | Warn: {sev_b.get('Warning',0)} | Info: {sev_b.get('Information',0)}"
        add_summary_row(self._vuln_card, 1, 0, "Severity Breakdown", sev_str)
        
        # Compliance Summary
        failed_validators = {f.validator for f in result.findings}
        
        def get_comp_stat(name):
            if name in failed_validators: return "Failed", get_color("CRITICAL")
            return "Pass", get_color("SUCCESS")

        cs_req, cs_req_c = get_comp_stat("Required Sections")
        cs_date, cs_date_c = get_comp_stat("Date Validation")
        cs_term, cs_term_c = get_comp_stat("Terminology Check")
        cs_spell, cs_spell_c = get_comp_stat("Spelling Check")

        add_summary_row(self._comp_card, 0, 0, "Required Sections", cs_req, cs_req_c)
        add_summary_row(self._comp_card, 0, 1, "Date", cs_date, cs_date_c)
        add_summary_row(self._comp_card, 0, 2, "Terminology", cs_term, cs_term_c)
        add_summary_row(self._comp_card, 0, 3, "Spelling", cs_spell, cs_spell_c)

        # Knowledge Discovery Review
        self._log_debug("Populating Knowledge Discovery candidates...")
        
        # Populate summary section metrics
        summary = getattr(result, "discovery_summary", {})
        total_found = summary.get("total_found", 0)
        filtered_count = summary.get("filtered_count", 0)
        eligible_count = summary.get("eligible_count", 0)
        
        self._val_cand_found.configure(text=str(total_found))
        self._val_cand_filtered.configure(text=str(filtered_count))
        self._val_cand_eligible.configure(text=str(eligible_count))
        self._val_cand_selected.configure(text="0")
        self._val_cand_updated.configure(text=datetime.now().strftime("%I:%M %p"))
        self._lbl_selected_counter.configure(text="Selected: 0")
        self._lbl_discovery_status.configure(text="Ready for Review", text_color=get_color("ACCENT"))
        
        for w in self._discovery_scroll.winfo_children():
            w.destroy()
            
        candidates = getattr(result, "discovery_candidates", [])
        if not candidates:
            lbl_empty = ctk.CTkLabel(self._discovery_scroll, text="No knowledge candidates detected for this scan.", font=get_font_body(), text_color=get_color("TEXT_SECONDARY"))
            lbl_empty.pack(padx=16, pady=16, anchor="w")
            self._enable_word_wrap(lbl_empty, padding=64)
        else:
            self._candidate_vars = {}
            groups = {"Organizations": [], "Products": [], "Acronyms": [], "Terms": []}
            for cand in candidates:
                cat = cand.get("type", "Terms")
                if cat not in groups:
                    cat = "Terms"
                groups[cat].append(cand)
                
            for cat_name, cat_cands in groups.items():
                cat_frame = ctk.CTkFrame(self._discovery_scroll, fg_color="transparent")
                cat_frame.pack(fill="x", pady=6)
                
                hdr = ctk.CTkFrame(cat_frame, fg_color="transparent")
                hdr.pack(fill="x", pady=4)
                
                lbl = ctk.CTkLabel(hdr, text=f"▼ {cat_name} ({len(cat_cands)})", font=get_font_body("bold"), text_color=get_color("TEXT_PRIMARY"))
                lbl.pack(side="left")
                self._enable_word_wrap(lbl, padding=160)
                
                controls = ctk.CTkFrame(hdr, fg_color="transparent")
                controls.pack(side="right")
                
                cat_vars = []
                cat_cards = []
                
                ctk.CTkButton(controls, text="Clear", width=50, height=20, font=get_font_caption(), fg_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"), hover_color=get_color("ROW_BG"), command=lambda cv=cat_vars, cc=cat_cards: [[v.set(False) for v in cv], [self._update_card_visuals(card, var) for card, var in cc], self._update_selected_count()]).pack(side="right")
                ctk.CTkButton(controls, text="Select All", width=60, height=20, font=get_font_caption(), fg_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"), hover_color=get_color("ROW_BG"), command=lambda cv=cat_vars, cc=cat_cards: [[v.set(True) for v in cv], [self._update_card_visuals(card, var) for card, var in cc], self._update_selected_count()]).pack(side="right", padx=(0, 4))
                
                content = ctk.CTkFrame(cat_frame, fg_color="transparent")
                
                # Priority 8: Empty Categories collapsed by default
                if len(cat_cands) == 0:
                    lbl.configure(text=f"▶ {cat_name} (0)")
                    content.pack_forget()
                else:
                    lbl.configure(text=f"▼ {cat_name} ({len(cat_cands)})")
                    content.pack(fill="x", pady=4)
                
                def make_toggle(l, c, name, count):
                    def toggle(e):
                        if c.winfo_ismapped():
                            c.pack_forget()
                            l.configure(text=f"▶ {name} ({count})")
                        else:
                            c.pack(fill="x", pady=4)
                            l.configure(text=f"▼ {name} ({count})")
                    return toggle
                lbl.bind("<Button-1>", make_toggle(lbl, content, cat_name, len(cat_cands)))
                lbl.configure(cursor="hand2")
                
                for cand in cat_cands:
                    term = cand["term"]
                    
                    # Custom Candidate Card (Priority 7)
                    card = ctk.CTkFrame(content, fg_color=get_color("APP_BG"), corner_radius=8, border_width=1, border_color=get_color("BORDER"))
                    card.pack(fill="x", pady=4)
                    card.grid_columnconfigure(1, weight=1)
                    
                    var = ctk.BooleanVar(value=False)
                    cat_vars.append(var)
                    self._candidate_vars[term] = (var, cand, card)
                    cat_cards.append((card, var))
                    
                    # Checkbox
                    cb = ctk.CTkCheckBox(card, text="", variable=var, width=20, fg_color=get_color("ACCENT"), hover_color=get_color("BORDER"))
                    cb.grid(row=0, column=0, rowspan=3, padx=(12, 8), pady=8, sticky="w")
                    
                    # Term Name with Truncation after 32 chars (Priority 5)
                    term_display = term
                    has_tooltip = False
                    if len(term) > 32:
                        term_display = term[:29] + "..."
                        has_tooltip = True
                        
                    lbl_name = ctk.CTkLabel(card, text=term_display, font=get_font_body("bold"), text_color=get_color("TEXT_PRIMARY"))
                    lbl_name.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(8, 2))
                    
                    if has_tooltip:
                        ToolTip(lbl_name, term)
                        
                    # Category label
                    lbl_cat = ctk.CTkLabel(card, text=cand.get("type", "Term"), font=get_font_caption(), text_color=get_color("TEXT_MUTED"))
                    lbl_cat.grid(row=1, column=1, sticky="w", padx=(0, 12), pady=0)
                    self._enable_word_wrap(lbl_cat, padding=80)
                    
                    # Metadata & Badge row
                    info_f = ctk.CTkFrame(card, fg_color="transparent")
                    info_f.grid(row=2, column=1, sticky="w", padx=(0, 12), pady=(2, 8))
                    
                    lbl_occ = ctk.CTkLabel(info_f, text=f"Occurrences: {cand['count']}  •  ", font=get_font_caption(), text_color=get_color("TEXT_SECONDARY"))
                    lbl_occ.pack(side="left")
                    self._enable_word_wrap(lbl_occ, padding=120)
                    
                    # Confidence Badge (Priority 1 confidence display)
                    conf = cand.get("confidence", "Medium")
                    if conf == "High":
                        bg = get_color("SUCCESS")
                        txt = "HIGH"
                    elif conf == "Medium":
                        bg = get_color("WARNING")
                        txt = "MED"
                    else:
                        bg = get_color("TEXT_MUTED")
                        txt = "LOW"
                        
                    badge = ctk.CTkFrame(info_f, fg_color=bg, corner_radius=4)
                    badge.pack(side="left")
                    ctk.CTkLabel(badge, text=txt, font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"), text_color="#FFFFFF").pack(padx=6, pady=1)
                    
                    # Bind check actions
                    cb.configure(command=lambda c=card, v=var: [self._update_card_visuals(c, v), self._update_selected_count()])
                    
                    # Bind interactive highlights and click to full card area
                    def bind_card_events(w):
                        w.bind("<Enter>", lambda e, c=card: c.configure(border_color=get_color("ACCENT")))
                        w.bind("<Leave>", lambda e, c=card, v=var: c.configure(border_color=get_color("BORDER")))
                        if w != cb:
                            w.bind("<Button-1>", lambda e, c=card, v=var: [v.set(not v.get()), self._update_card_visuals(c, v), self._update_selected_count()])
                            try:
                                w.configure(cursor="hand2")
                            except:
                                pass
                        for child in w.winfo_children():
                            bind_card_events(child)
                            
                    bind_card_events(card)

        # Recommendations list
        self._log_debug("Populating recommendations and detailed findings...")
        recs = [f for f in result.findings if getattr(f, "recommendation", "")]
        if not recs:
            ctk.CTkLabel(self._rec_card, text="✅ No critical recommendations. Keep up the good work!", font=get_font_body(), text_color=get_color("SUCCESS")).pack(padx=16, pady=16, anchor="w")
        else:
            for i, f in enumerate(recs):
                color = get_color("CRITICAL") if getattr(f, "severity", "") == "Critical" else get_color("WARNING") if getattr(f, "severity", "") == "Warning" else get_color("ACCENT")
                rf = ctk.CTkFrame(self._rec_card, fg_color="transparent")
                rf.pack(fill="x", padx=16, pady=(12 if i == 0 else 6, 12 if i == len(recs)-1 else 6))
                
                blt = ctk.CTkFrame(rf, fg_color=color, width=6, height=18, corner_radius=3)
                blt.pack(side="left", padx=(0, 12))
                ctk.CTkLabel(rf, text=getattr(f, "recommendation", ""), font=get_font_body(), text_color=get_color("TEXT_PRIMARY"), justify="left", wraplength=700).pack(side="left")

        if not result.findings:
            ctk.CTkLabel(self._findings_frame, text="✅ No findings detected! Document is fully compliant.", font=get_font_body(), text_color=get_color("SUCCESS")).pack(pady=40)
            return

        for f in result.findings:
            sev = getattr(f, "severity", "Information")
            if sev == "Critical": color = get_color("CRITICAL")
            elif sev == "Warning": color = get_color("WARNING")
            else: color = get_color("ACCENT")

            card = ctk.CTkFrame(self._findings_frame, fg_color=get_color("CARD_BG"), corner_radius=12, border_width=1, border_color=get_color("BORDER"))
            card.pack(fill="x", padx=12, pady=6)

            def on_enter(e, c=card):
                c.configure(fg_color=get_color("ROW_BG"), border_color=get_color("ACCENT"))

            def on_leave(e, c=card):
                x, y = c.winfo_pointerxy()
                target = c.winfo_containing(x, y)
                is_child = False
                temp = target
                while temp:
                    if temp == c:
                        is_child = True
                        break
                    try:
                        temp = temp.master
                    except AttributeError:
                        break
                if not is_child:
                    c.configure(fg_color=get_color("CARD_BG"), border_color=get_color("BORDER"))

            header = ctk.CTkFrame(card, fg_color="transparent")
            header.pack(fill="x", padx=16, pady=12)
            header.grid_columnconfigure(1, weight=1)

            badge = ctk.CTkFrame(header, fg_color=color, corner_radius=4)
            badge.grid(row=0, column=0, padx=(0, 16), sticky="nw")
            badge_text = sev.upper()
            if getattr(f, "validator", "") == "Branding Consistency Validation" and sev == "Critical":
                badge_text = "HIGH"
            ctk.CTkLabel(badge, text=badge_text, font=get_font_caption("bold"), text_color="#FFFFFF").pack(padx=8, pady=2)

            center_frame = ctk.CTkFrame(header, fg_color="transparent")
            center_frame.grid(row=0, column=1, sticky="w")
            
            title_container = ctk.CTkFrame(center_frame, fg_color="transparent")
            title_container.pack(anchor="w")
            
            indicator = ctk.CTkLabel(title_container, text="▶", font=get_font_h3(), text_color=get_color("TEXT_MUTED"))
            indicator.pack(side="left", padx=(0, 6))
            
            ctk.CTkLabel(title_container, text=getattr(f, "title", "Issue"), font=get_font_h3(), text_color=get_color("TEXT_PRIMARY")).pack(side="left")
            
            desc_text = getattr(f, "description", "")
            short_desc = (desc_text[:120] + "...") if len(desc_text) > 120 else desc_text
            ctk.CTkLabel(center_frame, text=short_desc, font=get_font_caption(), text_color=get_color("TEXT_MUTED"), justify="left").pack(anchor="w", pady=(4, 0))
            
            right_frame = ctk.CTkFrame(header, fg_color="transparent")
            right_frame.grid(row=0, column=2, sticky="ne")
            
            page_val, para_val = "N/A", "N/A"
            if getattr(f, "location", "") and "Page" in getattr(f, "location", ""):
                for p in getattr(f, "location", "").split(","):
                    if "Page" in p: page_val = p.replace("Page", "").strip()
                    elif "Paragraph" in p: para_val = p.replace("Paragraph", "").strip()
            
            if getattr(f, "validator", "") == "Branding Consistency Validation":
                location_display = f"Page {page_val}"
            else:
                location_display = f"Page {page_val} • Para {para_val}"
            ctk.CTkLabel(right_frame, text=location_display, font=get_font_caption("bold"), text_color=get_color("TEXT_MUTED")).pack(anchor="e")
            
            if getattr(f, "match_quality", ""):
                mq_col = get_color("SUCCESS") if getattr(f, "match_quality", "") in ("Excellent", "Strong") else get_color("WARNING") if getattr(f, "match_quality", "") == "Partial" else get_color("CRITICAL")
                ctk.CTkLabel(right_frame, text=getattr(f, "match_quality", ""), font=get_font_caption("bold"), text_color=mq_col).pack(anchor="e", pady=(4,0))

            body = ctk.CTkFrame(card, fg_color="transparent")

            def toggle_expand(e, b=body, ind=indicator):
                if b.winfo_ismapped():
                    b.pack_forget()
                    ind.configure(text="▶")
                else:
                    b.pack(fill="x", padx=16, pady=(0, 16))
                    ind.configure(text="▼")
            
            def bind_recursive(w):
                w.bind("<Button-1>", toggle_expand)
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)
                try:
                    w.configure(cursor="hand2")
                except Exception:
                    pass
                for c in w.winfo_children(): bind_recursive(c)
            bind_recursive(card)

            if getattr(f, "validator", "") == "Branding Consistency Validation" and getattr(f, "details", None):
                details = f.details
                
                info_frame = ctk.CTkFrame(body, fg_color=get_color("ROW_BG"), corner_radius=8, border_width=1, border_color=get_color("BORDER"))
                info_frame.pack(fill="x", pady=8, ipady=8, ipadx=12)
                
                def add_row(parent, label, value):
                    row = ctk.CTkFrame(parent, fg_color="transparent")
                    row.pack(fill="x", padx=12, pady=4)
                    ctk.CTkLabel(row, text=label, font=get_font_caption("bold"), text_color=get_color("TEXT_PRIMARY")).pack(side="left")
                    ctk.CTkLabel(row, text=value, font=get_font_caption(), text_color=get_color("TEXT_SECONDARY")).pack(side="right")
                    
                add_row(info_frame, "Expected Organization:", details.get("expected_org", ""))
                add_row(info_frame, "Detected Logo:", details.get("detected_logo", ""))
                add_row(info_frame, "Detection Confidence:", f"{details.get('confidence', 0)}%")
                add_row(info_frame, "Detection Method:", "Logo Matching")
                add_row(info_frame, "Page Number:", str(page_val))
                
                # Evidence (Page-level evidence)
                ctk.CTkLabel(body, text="Evidence", font=get_font_caption("bold"), text_color=get_color("TEXT_PRIMARY")).pack(anchor="w", pady=(12, 2))
                evidence_box = ctk.CTkFrame(body, fg_color=get_color("APP_BG"), corner_radius=8, border_width=1, border_color=get_color("BORDER"))
                evidence_box.pack(fill="x", pady=4, ipady=6, ipadx=12)
                
                for s in details.get("evidence_list", []):
                    line = ctk.CTkFrame(evidence_box, fg_color="transparent")
                    line.pack(fill="x", padx=12, pady=2)
                    ctk.CTkLabel(line, text=f"\u2022 Page {s['page']} \u2192 {details.get('detected_logo', '')}", font=get_font_caption(), text_color=get_color("TEXT_MUTED")).pack(side="left")
                    ctk.CTkLabel(line, text=f"Confidence: {int(s['confidence'])}%", font=get_font_caption("bold"), text_color=get_color("SUCCESS")).pack(side="right")
                
                # Recommendation
                rec = getattr(f, "recommendation", "")
                if rec:
                    ctk.CTkLabel(body, text="Recommendation", font=get_font_caption("bold"), text_color=get_color("TEXT_PRIMARY")).pack(anchor="w", pady=(12, 2))
                    ctk.CTkLabel(body, text=rec, font=get_font_caption(), text_color=get_color("TEXT_MUTED"), justify="left", wraplength=700).pack(anchor="w")
                
                # Explainability Block
                why_frame = ctk.CTkFrame(body, fg_color=get_color("APP_BG"), corner_radius=8, border_width=1, border_color=get_color("BORDER"))
                why_frame.pack(fill="x", pady=(16, 0), ipadx=8, ipady=8)
                
                ctk.CTkLabel(why_frame, text="\ud83e\udde0 Why This Is A Finding", font=get_font_caption("bold"), text_color=get_color("TEXT_PRIMARY")).pack(anchor="w", padx=12, pady=(8, 4))
                ctk.CTkLabel(why_frame, text=details.get("why_finding", ""), font=get_font_caption(), text_color=get_color("TEXT_MUTED"), justify="left", wraplength=680).pack(anchor="w", padx=12, pady=2)
                
                # Bind recursive interaction handlers to new UI elements
                bind_recursive(body)
            else:
                ctk.CTkLabel(body, text="Full Description", font=get_font_caption("bold"), text_color=get_color("TEXT_PRIMARY")).pack(anchor="w", pady=(8, 2))
                ctk.CTkLabel(body, text=desc_text, font=get_font_caption(), text_color=get_color("TEXT_MUTED"), justify="left", wraplength=700).pack(anchor="w")

                rec = getattr(f, "recommendation", "")
                if rec:
                    ctk.CTkLabel(body, text="Recommendation", font=get_font_caption("bold"), text_color=get_color("TEXT_PRIMARY")).pack(anchor="w", pady=(12, 2))
                    ctk.CTkLabel(body, text=rec, font=get_font_caption(), text_color=get_color("TEXT_MUTED"), justify="left", wraplength=700).pack(anchor="w")

            if getattr(f, "match_quality", ""):
                mq_frame = ctk.CTkFrame(body, fg_color=get_color("APP_BG"), corner_radius=8, border_width=1, border_color=get_color("BORDER"))
                mq_frame.pack(fill="x", pady=(16, 0), ipadx=8, ipady=8)
                bind_recursive(mq_frame) # Ensure inner items also toggle expansion
                
                hdr_f = ctk.CTkFrame(mq_frame, fg_color="transparent")
                hdr_f.pack(fill="x", padx=12, pady=(8, 4))
                ctk.CTkLabel(hdr_f, text="🧠 Intelligence Analysis", font=get_font_caption("bold"), text_color=get_color("TEXT_PRIMARY")).pack(side="left")
                
                if getattr(f, "match_quality", "") == "Unmatched":
                    ctk.CTkLabel(mq_frame, text=f"KB Match: No Reliable Match Found", font=get_font_caption("bold"), text_color=get_color("TEXT_PRIMARY")).pack(anchor="w", padx=12, pady=2)
                    
                    if getattr(f, "top_candidates", []):
                        ctk.CTkLabel(mq_frame, text="Top Candidates:", font=get_font_caption("bold"), text_color=get_color("TEXT_PRIMARY")).pack(anchor="w", padx=12, pady=(8,2))
                        for idx, cand in enumerate(getattr(f, "top_candidates", [])):
                            cand_text = f"{idx+1}. {cand['title']} (Score: {cand['score']}/100)"
                            ctk.CTkLabel(mq_frame, text=cand_text, font=get_font_caption(), text_color=get_color("TEXT_MUTED")).pack(anchor="w", padx=24, pady=1)
                            ctk.CTkLabel(mq_frame, text=f"   Rejection: {cand['reason']}", font=get_font_caption(), text_color=get_color("CRITICAL")).pack(anchor="w", padx=24, pady=(0,4))
                    else:
                        ctk.CTkLabel(mq_frame, text="Suggested Action: Review manually and consider adding a new vulnerability definition.", font=get_font_caption(), text_color=get_color("TEXT_MUTED"), justify="left").pack(anchor="w", padx=12, pady=(2, 8))
                else:
                    ctk.CTkLabel(mq_frame, text=f"KB Match: {getattr(f, 'matched_vulnerability', 'Unknown')}", font=get_font_caption("bold"), text_color=get_color("TEXT_PRIMARY")).pack(anchor="w", padx=12, pady=2)
                    
                    bd = getattr(f, "match_score_breakdown", {})
                    if bd:
                        score_txt = f"Score Breakdown: Title ({bd.get('title',0)}/30) | Desc ({bd.get('description',0)}/30) | Rem ({bd.get('remediation',0)}/25) | Sev ({bd.get('severity',0)}/15) = {bd.get('final',0)}/100"
                        ctk.CTkLabel(mq_frame, text=score_txt, font=get_font_caption("bold"), text_color=get_color("TEXT_PRIMARY")).pack(anchor="w", padx=12, pady=(6,2))

                    me = getattr(f, "match_evidence", {})
                    if me:
                        ctk.CTkLabel(mq_frame, text="Match Evidence:", font=get_font_caption("bold"), text_color=get_color("SUCCESS")).pack(anchor="w", padx=12, pady=(6,2))
                        if me.get("matched_keywords"): ctk.CTkLabel(mq_frame, text=f"• Keywords: {', '.join(me['matched_keywords'])}", font=get_font_caption(), text_color=get_color("TEXT_MUTED")).pack(anchor="w", padx=24, pady=1)
                        if me.get("matched_description_concepts"): ctk.CTkLabel(mq_frame, text=f"• Description Concepts: {', '.join(me['matched_description_concepts'])}", font=get_font_caption(), text_color=get_color("TEXT_MUTED")).pack(anchor="w", padx=24, pady=1)
                        if me.get("matched_remediation_concepts"): ctk.CTkLabel(mq_frame, text=f"• Remediation Concepts: {', '.join(me['matched_remediation_concepts'])}", font=get_font_caption(), text_color=get_color("TEXT_MUTED")).pack(anchor="w", padx=24, pady=1)

                    mis = getattr(f, "missing_evidence", {})
                    if mis:
                        ctk.CTkLabel(mq_frame, text="Missing Evidence (Lost Points):", font=get_font_caption("bold"), text_color=get_color("CRITICAL")).pack(anchor="w", padx=12, pady=(6,2))
                        for desc, pts in mis.items(): ctk.CTkLabel(mq_frame, text=f"• [-{pts}] {desc}", font=get_font_caption(), text_color=get_color("TEXT_MUTED")).pack(anchor="w", padx=24, pady=1)

        self._log_debug("Calling _boost_scroll on results container...")
        self._boost_scroll(self._results_container)

    def _open_exported_report(self):
        if hasattr(self, "_last_exported_path") and os.path.exists(self._last_exported_path):
            try:
                if sys.platform == "win32": os.startfile(self._last_exported_path)
                elif sys.platform == "darwin": subprocess.Popen(["open", self._last_exported_path])
                else: subprocess.Popen(["xdg-open", self._last_exported_path])
            except: pass

    def _submit_learning_queue(self):
        import os
        from datetime import datetime
        selected = []
        
        # Category mapping: singular terms expected by Rules tab
        cat_map = {
            "Organizations": "Organization",
            "Acronyms": "Acronym",
            "Products": "Term",
            "Terms": "Term"
        }
        
        for term, (var, cand, frame) in list(self._candidate_vars.items()):
            if var.get():
                raw_cat = cand.get("type", "Terms")
                mapped_cat = cat_map.get(raw_cat, "Term")
                
                new_cand = {
                    "term": cand["term"],
                    "type": mapped_cat,
                    "source_doc": os.path.basename(self._last_result.filename) if self._last_result else "Unknown",
                    "count": cand["count"],
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "status": "pending"
                }
                selected.append(new_cand)
                frame.destroy()
                del self._candidate_vars[term]
        
        if not selected:
            return
            
        from app.services.rules_loader import RulesLoader
        loader = RulesLoader()
        queue = loader.learning_queue
        queue.extend(selected)
        loader.save_learning_queue(queue)
        
        from app.utils.activity_helper import log_activity
        log_activity(f"Submitted {len(selected)} discovery candidates from {os.path.basename(self._last_result.filename) if self._last_result else 'scan'}", "Discovery Submitted")
        
        from app.ui.components import CustomDialog
        CustomDialog("Success", f"{len(selected)} items added to the Learning Queue.", "success").show()
        self._update_selected_count()

    def _export_report(self) -> None:
        if not self._last_result: return
        from app.utils.path_helper import get_reports_dir
        
        base_name = os.path.basename(self._last_result.filename)
        safe_name = os.path.splitext(base_name)[0].replace(" ", "_")

        save_path = filedialog.asksaveasfilename(
            initialdir=get_reports_dir(),
            initialfile=f"{safe_name}_compliance_report.pdf",
            title="Save Compliance Report",
            defaultextension=".pdf",
            filetypes=[("PDF Document", "*.pdf"), ("Word Document", "*.docx"), ("Text File", "*.txt")]
        )
        
        if not save_path:
            return

        ext = os.path.splitext(save_path)[1].lower()
        if ext == ".docx":
            format_type = "docx"
        elif ext == ".txt":
            format_type = "txt"
        else:
            format_type = "pdf"

        self._btn_export.configure(state="disabled", text="Exporting...")

        def _do_export():
            try:
                import time
                import json
                from app.utils.path_helper import get_data_dir

                start_t = time.perf_counter()
                export_report_to_path(self._last_result, format_type, save_path)
                export_time_ms = (time.perf_counter() - start_t) * 1000.0
                
                if not os.path.exists(save_path):
                    raise Exception(f"{format_type.upper()} generation succeeded, but the file was not found on disk.")

                # Read and update performance timings file
                perf_path = os.path.join(get_data_dir(), "last_scan_performance.json")
                perf_data = {}
                if os.path.exists(perf_path):
                    try:
                        with open(perf_path, "r", encoding="utf-8") as f:
                            perf_data = json.load(f)
                    except Exception:
                        pass
                
                perf_data["report_export_time_ms"] = export_time_ms
                try:
                    with open(perf_path, "w", encoding="utf-8") as f:
                        json.dump(perf_data, f, indent=2)
                except Exception:
                    pass

                dash = self._main_window._pages.get("dashboard")
                if dash: dash.update_last_export(save_path)

                reps = self._main_window._pages.get("reports")
                if reps: reps._refresh_list()

                def on_success():
                    self._btn_export.configure(state="normal", text="Export Report...")
                    self._status_badge.set_state("Exported")
                    self._last_exported_path = save_path
                    self._btn_open_report.pack(side="left")
                    
                    from app.ui.components import ExportSuccessDialog
                    from app.ui.theme import ThemeManager
                    import sys, subprocess
                    
                    tm = ThemeManager()
                    ui_settings = tm.get_setting("ui", {})
                    auto_open_pref = ui_settings.get("auto_open_exported_report", False)
                    
                    dialog = ExportSuccessDialog(file_path=save_path, initial_auto_open=auto_open_pref)
                    
                    if auto_open_pref:
                        try:
                            if sys.platform == "win32": os.startfile(save_path)
                            elif sys.platform == "darwin": subprocess.Popen(["open", save_path])
                            else: subprocess.Popen(["xdg-open", save_path])
                        except Exception:
                            dialog.set_warning("Report exported successfully but could not be opened automatically.")
                    
                    action, new_auto_open = dialog.show()
                    
                    if new_auto_open != auto_open_pref:
                        ui_settings["auto_open_exported_report"] = new_auto_open
                        tm.set_setting("ui", ui_settings)
                        tm.save()
                        
                    if action == "open_report":
                        self._open_exported_report()
                    elif action == "open_folder":
                        try:
                            if sys.platform == "win32":
                                subprocess.Popen(['explorer', f'/select,"{save_path}"'])
                            elif sys.platform == "darwin":
                                subprocess.Popen(["open", "-R", save_path])
                            else:
                                subprocess.Popen(["xdg-open", os.path.dirname(save_path)])
                        except Exception:
                            pass
                self.after(0, on_success)
            except Exception as e:
                err_msg = str(e)
                def on_error(err=err_msg):
                    self._btn_export.configure(state="normal", text="Export Report...")
                    CustomDialog("Export Failed", f"Could not generate report:\n{err}", "error").show()
                self.after(0, on_error)

        self._export_pool.submit(_do_export)

    def on_show(self) -> None:
        pass

    def get_state(self) -> dict:
        validator_states = {k: v.get() for k, v in self._validator_vars.items()}
        return {
            "scanner": self._scanner,
            "file_path": self._file_path,
            "last_result": self._last_result,
            "validator_states": validator_states,
            "status_badge_state": self._status_badge._lbl.cget("text") if hasattr(self, "_status_badge") else "READY",
            "last_progress_pct": getattr(self, "_last_progress_pct", 0.0)
        }

    def set_state(self, state: dict) -> None:
        self._scanner = state.get("scanner", self._scanner)
        self._file_path = state.get("file_path", "")
        self._last_result = state.get("last_result", None)
        
        # Restore validator check states
        validator_states = state.get("validator_states", {})
        for k, val in validator_states.items():
            if k in self._validator_vars:
                self._validator_vars[k].set(val)
                
        # Restore file selection info
        if self._file_path:
            self._file_label.configure(text=os.path.basename(self._file_path), text_color=get_color("TEXT_PRIMARY"))
            if os.path.exists(self._file_path):
                size_kb = os.path.getsize(self._file_path) / 1024
                self._file_size_label.configure(text=f"{size_kb:.1f} KB")
            else:
                self._file_size_label.configure(text="PDF or DOCX")
        
        # Restore badge state
        badge_state = state.get("status_badge_state", "READY").capitalize()
        self._status_badge.set_state(badge_state)
        
        # Restore results if scan was completed
        if self._last_result:
            self._populate_results(self._last_result)
            self._results_container.grid(row=6, column=0, padx=32, pady=(16, 48), sticky="ew")
            # Also show progress card as completed
            self._progress_card.grid()
            self._update_progress(1.0, "")
        elif self._scanner.is_running:
            # If scan was running, show progress card and restore last progress state
            self._progress_card.grid()
            self._scan_btn.configure(state="disabled")
            self._cancel_btn.configure(state="normal")
            pct = state.get("last_progress_pct", 0.0)
            self._update_progress(pct, "")
