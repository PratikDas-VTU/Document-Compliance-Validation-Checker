"""
dashboard.py — Enterprise Dashboard.
Phase 5C: Added Trend KPIs, KB Mini-Cards, and Timeline.
"""
from __future__ import annotations
import os
import json
import datetime
import subprocess
import sys
import customtkinter as ctk

from app.services.rules_loader import RulesLoader
from app.utils.path_helper import get_data_dir, get_reports_dir
from app.ui.theme import get_color, get_font_h1, get_font_h2, get_font_h3, get_font_body, get_font_caption, RADIUS, BORDER_WIDTH
from app.ui.components import StatusBadge

class CTkDoubleScrollableFrame(ctk.CTkFrame):
    def __init__(self, master, height=320, fg_color="transparent", **kwargs):
        super().__init__(master, fg_color=fg_color, **kwargs)
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        canvas_bg = get_color("CARD_BG")
        
        self.canvas = ctk.CTkCanvas(
            self,
            bg=canvas_bg,
            highlightthickness=0,
            borderwidth=0
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        
        self.vsb = ctk.CTkScrollbar(self, orientation="vertical", command=self.canvas.yview)
        self.vsb.grid(row=0, column=1, sticky="ns", padx=(4, 0))
        
        self.hsb = ctk.CTkScrollbar(self, orientation="horizontal", command=self.canvas.xview)
        self.hsb.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        
        self.canvas.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)
        
        self.scrollable_frame = ctk.CTkFrame(self.canvas, fg_color="transparent")
        self.window_id = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        self.scrollable_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        
        if height:
            self.canvas.configure(height=height)
            
        self.bind_mousewheel_to_all(self)
        self.bind_mousewheel_to_all(self.canvas)
        self.bind_mousewheel_to_all(self.vsb)
        self.bind_mousewheel_to_all(self.hsb)
        self.bind_mousewheel_to_all(self.scrollable_frame)

    def _on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        canvas_width = event.width
        frame_width = self.scrollable_frame.winfo_reqwidth()
        
        if frame_width < canvas_width:
            self.canvas.itemconfig(self.window_id, width=canvas_width)
        else:
            self.canvas.itemconfig(self.window_id, width=0)

    def bind_mousewheel_to_all(self, widget):
        widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
        if widget == self:
            children = [self.canvas, self.vsb, self.hsb, self.scrollable_frame]
        else:
            try:
                children = widget.winfo_children()
            except Exception:
                children = []
        for child in children:
            self.bind_mousewheel_to_all(child)

    def _on_mousewheel(self, event):
        import sys
        if sys.platform == "darwin":
            self.canvas.yview_scroll(int(-1 * event.delta), "units")
        else:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def winfo_children(self):
        return self.scrollable_frame.winfo_children()


class DashboardPage(ctk.CTkFrame):
    def __init__(self, parent, main_window, **kwargs):
        print("Dashboard Page Created")
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._main_window = main_window

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.grid(row=0, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        self._scan_log = []
        self._activity_log = []
        self._last_history_mtime = 0.0
        self._last_activity_mtime = 0.0
        self._last_rules_reload = -1
        self._last_kb_reload = -1
        self._load_data()

        self._build()

    def _load_data(self):
        log_path = os.path.join(get_data_dir(), "scan_history.json")
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    self._scan_log = json.load(f)
            except Exception:
                self._scan_log = []
                
        act_path = os.path.join(get_data_dir(), "activity_log.json")
        if os.path.exists(act_path):
            try:
                with open(act_path, "r", encoding="utf-8") as f:
                    self._activity_log = json.load(f)
            except Exception:
                self._activity_log = []

    def _add_activity(self, message: str, event_type: str):
        from app.utils.activity_helper import log_activity
        log_activity(message, event_type)

    def save_scan(self, filename: str, score: float, grade: str, critical: int, warning: int, info: int, avg_match_quality: float = 0.0, discovery_summary: dict = None):
        self._scan_log.insert(0, {
            "filename": os.path.basename(filename),
            "score": score,
            "grade": grade,
            "critical": critical,
            "warning": warning,
            "info": info,
            "avg_match_quality": avg_match_quality,
            "timestamp": datetime.datetime.now().isoformat(),
            "exported_path": None,
            "discovery_summary": discovery_summary
        })
        self._scan_log = self._scan_log[:50]
        
        log_path = os.path.join(get_data_dir(), "scan_history.json")
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(self._scan_log, f, indent=2)
        except Exception:
            pass

        # Persistent cumulative discovery stats update
        if discovery_summary:
            from app.utils.activity_helper import update_discovery_stats
            update_discovery_stats(
                discovered=discovery_summary.get("total_found", 0),
                filtered=discovery_summary.get("filtered_count", 0),
                eligible=discovery_summary.get("eligible_count", 0)
            )

        from app.utils.activity_helper import log_activity
        log_activity(f"Scan completed: {os.path.basename(filename)}", "Scan Completed", os.path.basename(filename))
        self._refresh()

    def update_last_export(self, pdf_path: str):
        if self._scan_log:
            from app.utils.path_helper import get_writable_base
            base = get_writable_base()
            try:
                abs_base = os.path.abspath(base)
                abs_pdf = os.path.abspath(pdf_path)
                if abs_pdf.lower().startswith(abs_base.lower()):
                    store_path = os.path.relpath(abs_pdf, abs_base)
                else:
                    store_path = pdf_path
            except Exception:
                store_path = pdf_path

            self._scan_log[0]["exported_path"] = store_path
            
            log_path = os.path.join(get_data_dir(), "scan_history.json")
            try:
                with open(log_path, "w", encoding="utf-8") as f:
                    json.dump(self._scan_log, f, indent=2)
            except Exception:
                pass
            
            from app.utils.activity_helper import log_activity
            log_activity(f"Exported: {os.path.basename(pdf_path)}", "Report Exported", os.path.basename(pdf_path))
            self._refresh()

    def _build(self) -> None:
        S = self._scroll

        # Page Header
        hdr = ctk.CTkFrame(S, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=32, pady=(28, 24), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(hdr, text="Platform Dashboard", font=get_font_h1(), text_color=get_color("TEXT_PRIMARY")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(hdr, text="Overview of platform health, knowledge base, and compliance metrics.", font=get_font_body(), text_color=get_color("TEXT_SECONDARY")).grid(row=1, column=0, sticky="w", pady=(4, 0))

        # Refresh Metrics Button
        btn_refresh = ctk.CTkButton(
            hdr, text="🔄 Refresh Metrics", font=get_font_body("bold"), height=36, corner_radius=8,
            fg_color=get_color("ROW_BG"), hover_color=get_color("BORDER"),
            text_color=get_color("TEXT_PRIMARY"),
            command=self._refresh
        )
        btn_refresh.grid(row=0, column=1, rowspan=2, sticky="e")

        btn_scan = ctk.CTkButton(
            hdr, text="▶ New Scan", font=get_font_body("bold"), height=36, corner_radius=8,
            fg_color=get_color("ACCENT"), hover_color=get_color("BORDER"),
            command=lambda: self._main_window.show_page("scan")
        )
        btn_scan.grid(row=0, column=2, rowspan=2, sticky="e", padx=(12, 0))

        # ── KPI Row (Operational Metrics) ─────────────────────────────────────
        self._kpi_frame = ctk.CTkFrame(S, fg_color="transparent")
        self._kpi_frame.grid(row=1, column=0, padx=32, pady=(0, 24), sticky="ew")
        for i in range(4):
            self._kpi_frame.grid_columnconfigure(i, weight=1)

        self._lbls_kpi = {}
        self._lbls_trend = {}

        for i, key in enumerate(["scans", "score", "critical", "match"]):
            card = ctk.CTkFrame(self._kpi_frame, fg_color=get_color("CARD_BG"), corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=get_color("BORDER"))
            card.grid(row=0, column=i, padx=(0, 16) if i < 3 else 0, sticky="ew")
            
            hdr_f = ctk.CTkFrame(card, fg_color="transparent")
            hdr_f.pack(fill="x", padx=20, pady=(20, 4))
            
            title = ["Documents Scanned", "Compliance Score", "Critical Issues", "Avg Match Confidence"][i]
            ctk.CTkLabel(hdr_f, text=title, font=get_font_caption(), text_color=get_color("TEXT_SECONDARY")).pack(side="left")
            
            trend = ctk.CTkLabel(hdr_f, text="", font=get_font_caption("bold"))
            trend.pack(side="right")
            self._lbls_trend[key] = trend

            val = ctk.CTkLabel(card, text="0", font=get_font_h1(), text_color=get_color("TEXT_PRIMARY"))
            val.pack(anchor="w", padx=20, pady=(0, 20))
            self._lbls_kpi[key] = val

        # ── Middle Row (3-Column Layout) ──────────────────────────────────────
        mid_frame = ctk.CTkFrame(S, fg_color="transparent")
        mid_frame.grid(row=2, column=0, padx=32, pady=(0, 24), sticky="ew")
        mid_frame.grid_columnconfigure((0, 1, 2), weight=1)
        mid_frame.grid_rowconfigure(0, weight=1)

        # Helper to layout metric cards in wrapping grid
        def layout_flow(container, frames, min_width=130):
            def on_configure(event):
                w = event.width
                cols = max(1, w // min_width)
                for c in range(20):
                    container.grid_columnconfigure(c, weight=0)
                for c in range(cols):
                    container.grid_columnconfigure(c, weight=1)
                for idx, f in enumerate(frames):
                    r = idx // cols
                    c = idx % cols
                    f.grid(row=r, column=c, padx=6, pady=6, sticky="ew")
            container.bind("<Configure>", on_configure, add="+")

        # Knowledge Base Statistics (Column 0)
        kb_card = ctk.CTkFrame(mid_frame, fg_color=get_color("CARD_BG"), corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=get_color("BORDER"))
        kb_card.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        kb_card.grid_columnconfigure(0, weight=1)
        kb_card.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(kb_card, text="Knowledge Base Statistics", font=get_font_h3(), text_color=get_color("TEXT_PRIMARY")).grid(row=0, column=0, padx=24, pady=(20, 16), sticky="w")

        kb_container = ctk.CTkFrame(kb_card, fg_color="transparent")
        kb_container.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        kb_container.grid_columnconfigure(0, weight=1)

        self._lbls_kb = {}
        kb_keys = [
            ("dict", "Dictionary Words"), ("cyb", "Cyber Terms"), ("acr", "Acronyms"),
            ("org", "Organizations"), ("req", "Req Sections"), ("vul", "Vulnerability KB"),
            ("log", "Organization Logos"), ("act", "Active Validators")
        ]
        
        kb_card_frames = []
        for k, t in kb_keys:
            f = ctk.CTkFrame(kb_container, fg_color=get_color("ROW_BG"), corner_radius=8)
            v = ctk.CTkLabel(f, text="0", font=get_font_h2(), text_color=get_color("TEXT_PRIMARY"))
            v.pack(pady=(12, 0))
            ctk.CTkLabel(f, text=t, font=get_font_caption(), text_color=get_color("TEXT_SECONDARY")).pack(pady=(0, 12))
            self._lbls_kb[k] = v
            kb_card_frames.append(f)
        
        layout_flow(kb_container, kb_card_frames)

        # Knowledge Discovery & Learning Queue Metrics (Column 1)
        disc_card = ctk.CTkFrame(mid_frame, fg_color=get_color("CARD_BG"), corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=get_color("BORDER"))
        disc_card.grid(row=0, column=1, sticky="nsew", padx=(0, 16))
        disc_card.grid_columnconfigure(0, weight=1)
        disc_card.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(disc_card, text="Knowledge Discovery & Queue", font=get_font_h3(), text_color=get_color("TEXT_PRIMARY")).grid(row=0, column=0, padx=24, pady=(20, 16), sticky="w")

        disc_container = ctk.CTkFrame(disc_card, fg_color="transparent")
        disc_container.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        disc_container.grid_columnconfigure(0, weight=1)

        self._lbls_disc = {}
        disc_keys = [
            ("disc_discovered", "Candidates Discovered"), ("disc_filtered", "Candidates Filtered"),
            ("disc_eligible", "Eligible Candidates"), ("disc_pending", "Pending Reviews"),
            ("disc_approved", "Approved Items"), ("disc_rejected", "Rejected Items")
        ]

        disc_card_frames = []
        for k, t in disc_keys:
            f = ctk.CTkFrame(disc_container, fg_color=get_color("ROW_BG"), corner_radius=8)
            v = ctk.CTkLabel(f, text="0", font=get_font_h2(), text_color=get_color("TEXT_PRIMARY"))
            v.pack(pady=(12, 0))
            ctk.CTkLabel(f, text=t, font=get_font_caption(), text_color=get_color("TEXT_SECONDARY")).pack(pady=(0, 12))
            self._lbls_disc[k] = v
            disc_card_frames.append(f)
            
        layout_flow(disc_container, disc_card_frames)

        # Recent Activity (Column 2)
        act_card = ctk.CTkFrame(mid_frame, fg_color=get_color("CARD_BG"), corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=get_color("BORDER"))
        act_card.grid(row=0, column=2, sticky="nsew")
        act_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(act_card, text="Recent Activity", font=get_font_h3(), text_color=get_color("TEXT_PRIMARY")).grid(row=0, column=0, padx=24, pady=(20, 16), sticky="w")

        self._act_container = CTkDoubleScrollableFrame(act_card, fg_color="transparent", height=320)
        self._act_container.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 16))
        self._act_container.grid_columnconfigure(0, weight=1)

        # ── Bottom Row ────────────────────────────────────────────────────────
        bot_frame = ctk.CTkFrame(S, fg_color="transparent")
        bot_frame.grid(row=3, column=0, padx=32, pady=(0, 32), sticky="ew")
        bot_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        def btn_qa(col, text, cmd, is_primary=False):
            color = get_color("ACCENT") if is_primary else get_color("ROW_BG")
            b = ctk.CTkButton(bot_frame, text=text, font=get_font_body("bold"), height=44, corner_radius=8, fg_color=color, hover_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"), command=cmd)
            b.grid(row=0, column=col, padx=(0, 16) if col < 3 else 0, sticky="ew")
            return b

        self._btn_last_rep = btn_qa(0, "📄 Open Last Report", self._open_last_report, True)
        btn_qa(1, "📁 Open Reports Folder", self._open_reports_dir)
        btn_qa(2, "🔄 Reload Rules Engine", self._reload_rules)
        btn_qa(3, "⚙️ Platform Settings", lambda: self._main_window.show_page("settings"))

        self._refresh()

    def _populate_activity(self):
        for w in self._act_container.winfo_children():
            w.destroy()

        if not self._activity_log:
            empty = ctk.CTkFrame(self._act_container.scrollable_frame, fg_color="transparent")
            empty.pack(expand=True, fill="both", pady=40)
            
            ico = ctk.CTkLabel(empty, text="📋", font=("Segoe UI", 48))
            ico.pack(pady=(0, 16))
            
            ctk.CTkLabel(empty, text="No Validation Activity Yet", font=get_font_h3(), text_color=get_color("TEXT_PRIMARY")).pack(pady=(0, 4))
            ctk.CTkLabel(empty, text="Upload a PDF or DOCX document to begin compliance analysis.", font=get_font_body(), text_color=get_color("TEXT_SECONDARY"), wraplength=200).pack()
            self._btn_last_rep.configure(state="disabled", text="📄 No reports generated yet")
            self._act_container.bind_mousewheel_to_all(self._act_container.scrollable_frame)
            return

        self._btn_last_rep.configure(
            state="normal" if self._scan_log and self._scan_log[0].get("exported_path") else "disabled",
            text="📄 Open Last Report"
        )

        for idx, act in enumerate(self._activity_log[:15]):
            row = ctk.CTkFrame(self._act_container.scrollable_frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=8)
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(row, text="✓", font=get_font_body("bold"), text_color=get_color("SUCCESS")).grid(row=0, column=0, sticky="n", padx=(0, 12))
            
            text_frame = ctk.CTkFrame(row, fg_color="transparent")
            text_frame.grid(row=0, column=1, sticky="w")
            
            ctk.CTkLabel(text_frame, text=act.get("message", ""), font=get_font_body(), text_color=get_color("TEXT_PRIMARY"), justify="left").pack(anchor="w")
            
            try:
                dt = datetime.datetime.fromisoformat(act.get("timestamp", ""))
                time_str = dt.strftime("%Y-%m-%d %H:%M")
            except:
                time_str = "Unknown time"
            
            act_type = act.get("activity_type") or act.get("type", "Info")
            ctk.CTkLabel(text_frame, text=f"{act_type}  •  {time_str}", font=get_font_caption(), text_color=get_color("TEXT_SECONDARY")).pack(anchor="w")

        self._act_container.bind_mousewheel_to_all(self._act_container.scrollable_frame)

    def _refresh(self):
        import os
        from app.utils.path_helper import get_data_dir
        from app.utils.activity_helper import get_learning_stats, get_discovery_stats
        
        hist_path = os.path.join(get_data_dir(), "scan_history.json")
        act_path = os.path.join(get_data_dir(), "activity_log.json")
        self._last_history_mtime = os.path.getmtime(hist_path) if os.path.exists(hist_path) else 0.0
        self._last_activity_mtime = os.path.getmtime(act_path) if os.path.exists(act_path) else 0.0
        
        loader = RulesLoader()
        loader.reload()
        
        self._last_rules_reload = loader.rules_reload_count
        self._last_kb_reload = loader.kb_reload_count

        self._load_data()
        
        # Calculate Trends
        total_scans = len(self._scan_log)
        
        scans_this_week = 0
        scans_last_week = 0
        now = datetime.datetime.now()
        for s in self._scan_log:
            try:
                dt = datetime.datetime.fromisoformat(s.get("timestamp"))
                if (now - dt).days <= 7: scans_this_week += 1
                elif (now - dt).days <= 14: scans_last_week += 1
            except: pass

        avg_score = sum(s.get("score", 0) for s in self._scan_log) / total_scans if total_scans else 0
        avg_score_prev = sum(s.get("score", 0) for s in self._scan_log[1:]) / (total_scans - 1) if total_scans > 1 else avg_score
        score_diff = avg_score - avg_score_prev
        
        total_crit = sum(s.get("critical", 0) for s in self._scan_log)
        total_crit_prev = sum(s.get("critical", 0) for s in self._scan_log[1:]) if total_scans > 1 else total_crit
        crit_diff = total_crit - total_crit_prev
        
        scans_with_mq = [s for s in self._scan_log if s.get("avg_match_quality", 0) > 0]
        avg_match = sum(s["avg_match_quality"] for s in scans_with_mq) / len(scans_with_mq) if scans_with_mq else 0
        avg_match_prev = sum(s["avg_match_quality"] for s in scans_with_mq[1:]) / (len(scans_with_mq) - 1) if len(scans_with_mq) > 1 else avg_match
        match_diff = avg_match - avg_match_prev

        stats = loader.stats()
        logos_meta = loader.get_logo_repository_metadata()
        l_stats = get_learning_stats()
        d_stats = get_discovery_stats()

        # Update KPIs
        self._lbls_kpi["scans"].configure(text=str(total_scans))
        scan_trend = f"↑ +{scans_this_week}" if scans_this_week > scans_last_week else (f"↓ {scans_this_week - scans_last_week}" if scans_this_week < scans_last_week else "—")
        self._lbls_trend["scans"].configure(text=scan_trend, text_color=get_color("SUCCESS") if "+" in scan_trend else get_color("TEXT_SECONDARY"))

        if total_scans == 0:
            self._lbls_kpi["score"].configure(text="--", text_color=get_color("TEXT_SECONDARY"))
            self._lbls_trend["score"].configure(text="—", text_color=get_color("TEXT_SECONDARY"))
            self._lbls_kpi["critical"].configure(text="--", text_color=get_color("TEXT_SECONDARY"))
            self._lbls_trend["critical"].configure(text="—", text_color=get_color("TEXT_SECONDARY"))
            self._lbls_kpi["match"].configure(text="--", text_color=get_color("TEXT_SECONDARY"))
            self._lbls_trend["match"].configure(text="—", text_color=get_color("TEXT_SECONDARY"))
        else:
            self._lbls_kpi["score"].configure(text=f"{avg_score:.1f}%", text_color=get_color("SUCCESS") if avg_score >= 80 else get_color("WARNING"))
            st_color = get_color("SUCCESS") if score_diff >= 0 else get_color("CRITICAL")
            self._lbls_trend["score"].configure(text=f"↑ +{score_diff:.1f}%" if score_diff >= 0 else f"↓ {score_diff:.1f}%", text_color=st_color if total_scans > 1 else get_color("TEXT_SECONDARY"))

            self._lbls_kpi["critical"].configure(text=str(total_crit), text_color=get_color("CRITICAL") if total_crit > 0 else get_color("SUCCESS"))
            c_color = get_color("CRITICAL") if crit_diff > 0 else get_color("SUCCESS")
            self._lbls_trend["critical"].configure(text=f"↑ +{crit_diff}" if crit_diff > 0 else f"↓ {crit_diff}", text_color=c_color if total_scans > 1 else get_color("TEXT_SECONDARY"))

            if avg_match > 0:
                self._lbls_kpi["match"].configure(text=f"{avg_match:.1f}%", text_color=get_color("SUCCESS") if avg_match >= 75 else get_color("WARNING"))
                m_color = get_color("SUCCESS") if match_diff >= 0 else get_color("WARNING")
                self._lbls_trend["match"].configure(text=f"↑ +{match_diff:.1f}%" if match_diff >= 0 else f"↓ {match_diff:.1f}%", text_color=m_color if len(scans_with_mq) > 1 else get_color("TEXT_SECONDARY"))
            else:
                self._lbls_kpi["match"].configure(text="--", text_color=get_color("TEXT_SECONDARY"))
                self._lbls_trend["match"].configure(text="No Matches", text_color=get_color("TEXT_SECONDARY"))

        # Calculate Active Validators
        active_validators = 0
        for key in ["required_section_validation", "date_validation", "vulnerability_validation", "terminology_validation", "spelling_validation", "empty_page_validation", "serial_number_validation", "page_number_validation", "branding_validation"]:
            rule = loader.custom_rules.get(key, {})
            default_val = False if key == "page_number_validation" else True
            if rule.get("enabled", default_val):
                active_validators += 1

        # Update KB Cards
        self._lbls_kb["dict"].configure(text=str(stats.get("standard_english", 0)))
        self._lbls_kb["cyb"].configure(text=str(stats.get("cybersecurity_terms", 0)))
        self._lbls_kb["acr"].configure(text=str(stats.get("acronyms", 0)))
        self._lbls_kb["org"].configure(text=str(stats.get("organization_terms", 0)))
        self._lbls_kb["req"].configure(text=str(len(stats.get("required_sections", []))))
        self._lbls_kb["vul"].configure(text=str(stats.get("vulnerabilities", 0)))
        self._lbls_kb["log"].configure(text=str(logos_meta.get("count", 0)))
        self._lbls_kb["act"].configure(text=str(active_validators))

        # Update Discovery/Queue Cards
        self._lbls_disc["disc_discovered"].configure(text=str(d_stats.get("total_discovered", 0)))
        self._lbls_disc["disc_filtered"].configure(text=str(d_stats.get("total_filtered", 0)))
        self._lbls_disc["disc_eligible"].configure(text=str(d_stats.get("total_eligible", 0)))
        self._lbls_disc["disc_pending"].configure(text=str(len(loader.learning_queue)))
        self._lbls_disc["disc_approved"].configure(text=str(l_stats.get("approved_count", 0)))
        self._lbls_disc["disc_rejected"].configure(text=str(l_stats.get("rejected_count", 0)))

        self._populate_activity()

    def on_show(self) -> None:
        import os
        from app.utils.path_helper import get_data_dir
        
        hist_path = os.path.join(get_data_dir(), "scan_history.json")
        act_path = os.path.join(get_data_dir(), "activity_log.json")
        
        hist_mtime = os.path.getmtime(hist_path) if os.path.exists(hist_path) else 0.0
        act_mtime = os.path.getmtime(act_path) if os.path.exists(act_path) else 0.0
        
        loader = RulesLoader()
        rules_reload = loader.rules_reload_count
        kb_reload = loader.kb_reload_count
        
        if (hist_mtime != self._last_history_mtime or 
            act_mtime != self._last_activity_mtime or 
            rules_reload != self._last_rules_reload or
            kb_reload != self._last_kb_reload):
            self._refresh()

    def _open_last_report(self):
        if not self._scan_log: return
        path = self._scan_log[0].get("exported_path")
        if not path:
            return
            
        from app.utils.path_helper import get_writable_base
        if not os.path.isabs(path):
            resolved_path = os.path.abspath(os.path.join(get_writable_base(), path))
        else:
            resolved_path = path
            if not os.path.exists(resolved_path):
                parts = resolved_path.split(os.sep)
                if "reports" in parts:
                    idx = parts.index("reports")
                    sub_path = os.path.join(*parts[idx:])
                    alt_path = os.path.abspath(os.path.join(get_writable_base(), sub_path))
                    if os.path.exists(alt_path):
                        resolved_path = alt_path

        if not os.path.exists(resolved_path):
            from app.ui.components import CustomDialog
            CustomDialog("Report Not Found", f"The exported report no longer exists at:\n{resolved_path}\n\nIt may have been moved or deleted.", "warning").show()
            return
        try:
            if sys.platform == "win32": os.startfile(resolved_path)
            elif sys.platform == "darwin": subprocess.Popen(["open", resolved_path])
            else: subprocess.Popen(["xdg-open", resolved_path])
        except Exception:
            pass
            pass

    def _open_reports_dir(self):
        path = get_reports_dir()
        try:
            if sys.platform == "win32": subprocess.Popen(["explorer", path])
            elif sys.platform == "darwin": subprocess.Popen(["open", path])
            else: subprocess.Popen(["xdg-open", path])
        except Exception:
            pass

    def _reload_rules(self):
        RulesLoader().load_all()
        from app.utils.activity_helper import log_activity
        log_activity("Knowledge Base rules reloaded", "Rule Reloaded")
        self._refresh()
