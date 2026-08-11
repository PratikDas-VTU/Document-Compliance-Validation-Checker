"""
developer_diagnostics.py — Developer Diagnostics page.
Contains KB Health, Match Statistics, Performance Metrics, Storage diagnostics, and collapsible Advanced Diagnostics.
"""
from __future__ import annotations
import os
import json
import time
import datetime
import customtkinter as ctk

from app.services.rules_loader import RulesLoader
from app.utils.path_helper import (
    get_rules_path, get_data_path, get_reports_path,
    get_exports_path, get_logo_repository_path, get_assets_path,
    get_logs_path
)
from app.ui.theme import (
    get_color, get_font_h1, get_font_h2, get_font_h3,
    get_font_body, get_font_caption, RADIUS, BORDER_WIDTH,
)
from app.ui.components import StatusBadge

class DeveloperDiagnosticsPage(ctk.CTkFrame):
    def __init__(self, parent, main_window, **kwargs):
        print("Developer Diagnostics Page Created")
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._main_window = main_window
        self._loader = RulesLoader()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.grid(row=0, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        # Advanced section state
        self._adv_expanded = False

        self._build()

    def _build(self) -> None:
        S = self._scroll

        # Page Header
        hdr = ctk.CTkFrame(S, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=32, pady=(28, 20), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(hdr, text="Developer Diagnostics", font=get_font_h1(), text_color=get_color("TEXT_PRIMARY")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(hdr, text="System telemetry, knowledge base health metrics, and engine performance audit.", font=get_font_body(), text_color=get_color("TEXT_SECONDARY")).grid(row=1, column=0, sticky="w", pady=(4, 0))

        # ─── Grid container for top cards ────────────────────────────────────
        self._cards_container = ctk.CTkFrame(S, fg_color="transparent")
        self._cards_container.grid(row=1, column=0, padx=32, pady=(0, 24), sticky="ew")
        self._cards_container.grid_columnconfigure((0, 1), weight=1)

        # Row 0, Column 0-1: Application Health Card (Spans both columns)
        self._build_health_card()

        # Row 1, Column 0: KB Health
        self._build_kb_health_card()

        # Row 1, Column 1: Match Engine Stats
        self._build_match_stats_card()

        # Row 2, Column 0: Performance Metrics
        self._build_performance_card()

        # Row 2, Column 1: Storage & RulesLoader Verification
        self._build_storage_loader_card()

        # Row 3: Branding Consistency Engine Card
        self._build_branding_card()

        # ─── Collapsible Advanced Diagnostics ────────────────────────────────
        self._build_collapsible_section()

        self._refresh_all()

    # ─── Cards Building ───────────────────────────────────────────────────────

    def _build_health_card(self) -> None:
        self._health_card = ctk.CTkFrame(self._cards_container, fg_color=get_color("CARD_BG"), corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=get_color("BORDER"))
        self._health_card.grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky="ew")
        self._health_card.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        ctk.CTkLabel(self._health_card, text="Application Health Status", font=get_font_h2(), text_color=get_color("TEXT_PRIMARY")).grid(row=0, column=0, columnspan=5, padx=24, pady=(20, 8), sticky="w")

        # Health checks: KB Integrity, Storage Paths, Report Storage, Match Engine, Performance
        self._health_labels = {}
        checks = [
            ("kb", "KB Integrity"),
            ("storage", "Storage Paths"),
            ("reports", "Report Storage"),
            ("engine", "Match Engine"),
            ("perf", "Performance")
        ]

        for col, (key, title) in enumerate(checks):
            f = ctk.CTkFrame(self._health_card, fg_color=get_color("ROW_BG"), corner_radius=8)
            f.grid(row=1, column=col, padx=(24 if col == 0 else 8, 24 if col == 4 else 8), pady=(0, 20), sticky="ew")
            
            ctk.CTkLabel(f, text=title, font=get_font_caption("bold"), text_color=get_color("TEXT_SECONDARY")).pack(pady=(12, 4))
            
            badge_f = ctk.CTkFrame(f, fg_color="transparent")
            badge_f.pack(pady=(0, 12))
            
            badge = StatusBadge(badge_f, state="Ready")
            badge.pack()
            self._health_labels[key] = badge

        # Overall Status Panel at bottom of health card
        overall_panel = ctk.CTkFrame(self._health_card, fg_color="transparent")
        overall_panel.grid(row=2, column=0, columnspan=5, padx=24, pady=(0, 20), sticky="ew")
        
        ctk.CTkLabel(overall_panel, text="Overall System Status:", font=get_font_body("bold"), text_color=get_color("TEXT_PRIMARY")).pack(side="left")
        self._overall_status_lbl = ctk.CTkLabel(overall_panel, text="Healthy", font=get_font_body("bold"), text_color=get_color("SUCCESS"))
        self._overall_status_lbl.pack(side="left", padx=8)

    def _build_kb_health_card(self) -> None:
        card = ctk.CTkFrame(self._cards_container, fg_color=get_color("CARD_BG"), corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=get_color("BORDER"))
        card.grid(row=1, column=0, padx=(0, 10), pady=(0, 20), sticky="nsew")
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="Knowledge Base Health", font=get_font_h3(), text_color=get_color("TEXT_PRIMARY")).grid(row=0, column=0, columnspan=2, padx=24, pady=(20, 12), sticky="w")

        metrics = [
            ("kb_loaded", "Loaded Vulnerabilities:"),
            ("kb_duplicates_id", "Duplicate IDs Detected:"),
            ("kb_duplicates_title", "Duplicate Titles Detected:"),
            ("kb_missing_kws", "Missing Keywords:"),
            ("kb_missing_desc", "Missing Descriptions:"),
            ("kb_missing_rem", "Missing Remediations:"),
            ("kb_status", "Integrity Warning Count:")
        ]

        self._kb_health_labels = {}
        for idx, (key, label) in enumerate(metrics):
            ctk.CTkLabel(card, text=label, font=get_font_body(), text_color=get_color("TEXT_SECONDARY")).grid(row=idx+1, column=0, padx=24, pady=6, sticky="w")
            val = ctk.CTkLabel(card, text="0", font=get_font_body("bold"), text_color=get_color("TEXT_PRIMARY"))
            val.grid(row=idx+1, column=1, padx=24, pady=6, sticky="e")
            self._kb_health_labels[key] = val

    def _build_match_stats_card(self) -> None:
        card = ctk.CTkFrame(self._cards_container, fg_color=get_color("CARD_BG"), corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=get_color("BORDER"))
        card.grid(row=1, column=1, padx=(10, 0), pady=(0, 20), sticky="nsew")
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="Matching Statistics (Last Scan)", font=get_font_h3(), text_color=get_color("TEXT_PRIMARY")).grid(row=0, column=0, columnspan=2, padx=24, pady=(20, 12), sticky="w")

        metrics = [
            ("scan_findings", "Total Detected Findings:"),
            ("scan_matched", "Matched Findings:"),
            ("scan_unmatched", "Unmatched Findings:"),
            ("scan_avg_quality", "Average Match Quality:"),
            ("scan_excellent", "Excellent Matches:"),
            ("scan_strong", "Strong Matches:"),
            ("scan_partial", "Partial Matches:")
        ]

        self._match_stats_labels = {}
        for idx, (key, label) in enumerate(metrics):
            ctk.CTkLabel(card, text=label, font=get_font_body(), text_color=get_color("TEXT_SECONDARY")).grid(row=idx+1, column=0, padx=24, pady=6, sticky="w")
            val = ctk.CTkLabel(card, text="0", font=get_font_body("bold"), text_color=get_color("TEXT_PRIMARY"))
            val.grid(row=idx+1, column=1, padx=24, pady=6, sticky="e")
            self._match_stats_labels[key] = val

    def _build_performance_card(self) -> None:
        card = ctk.CTkFrame(self._cards_container, fg_color=get_color("CARD_BG"), corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=get_color("BORDER"))
        card.grid(row=2, column=0, padx=(0, 10), pady=(0, 20), sticky="nsew")
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="Performance Metrics & Nav Stats", font=get_font_h3(), text_color=get_color("TEXT_PRIMARY")).grid(row=0, column=0, columnspan=2, padx=24, pady=(20, 12), sticky="w")

        metrics = [
            ("perf_parse", "PDF Parse Time:"),
            ("perf_load", "Rule Load Time:"),
            ("perf_match", "Match Engine Time:"),
            ("perf_export", "Report Export Time:"),
            ("perf_total", "Total Scan Time:"),
            ("nav_last", "Last Navigation Switch:"),
            ("nav_avg", "Average Navigation Switch:"),
            ("nav_worst", "Worst Navigation Switch:")
        ]

        self._perf_labels = {}
        for idx, (key, label) in enumerate(metrics):
            ctk.CTkLabel(card, text=label, font=get_font_body(), text_color=get_color("TEXT_SECONDARY")).grid(row=idx+1, column=0, padx=24, pady=6, sticky="w")
            val = ctk.CTkLabel(card, text="0 ms", font=get_font_body("bold"), text_color=get_color("TEXT_PRIMARY"))
            val.grid(row=idx+1, column=1, padx=24, pady=6, sticky="e")
            self._perf_labels[key] = val

    def _build_storage_loader_card(self) -> None:
        card = ctk.CTkFrame(self._cards_container, fg_color=get_color("CARD_BG"), corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=get_color("BORDER"))
        card.grid(row=2, column=1, padx=(10, 0), pady=(0, 20), sticky="nsew")
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="Storage & RulesLoader Verification", font=get_font_h3(), text_color=get_color("TEXT_PRIMARY")).grid(row=0, column=0, columnspan=2, padx=24, pady=(20, 12), sticky="w")

        metrics = [
            ("path_rules", "Rules Directory:"),
            ("path_data", "Data Directory:"),
            ("path_reports", "Reports Directory:"),
            ("path_exports", "Exports Directory:"),
            ("path_logos", "Organization Logos Directory:"),
            ("path_assets", "Assets Directory:"),
            ("path_learning", "Learning Queue Storage:"),
            ("path_manifest", "Runtime Manifest:"),
            ("loader_rules_reload", "Rules Reload Count:"),
            ("loader_kb_reload", "KB Reload Count:"),
            ("loader_last_time", "Last Reload Time:"),
        ]

        self._storage_labels = {}
        for idx, (key, label) in enumerate(metrics):
            ctk.CTkLabel(card, text=label, font=get_font_body(), text_color=get_color("TEXT_SECONDARY")).grid(row=idx+1, column=0, padx=24, pady=6, sticky="nw")
            if key.startswith("path_"):
                val = ctk.CTkLabel(card, text="N/A", font=get_font_caption(), text_color=get_color("TEXT_PRIMARY"), justify="right", wraplength=260)
            else:
                val = ctk.CTkLabel(card, text="0", font=get_font_body("bold"), text_color=get_color("TEXT_PRIMARY"))
            val.grid(row=idx+1, column=1, padx=24, pady=6, sticky="ne")
            self._storage_labels[key] = val

    def _build_branding_card(self) -> None:
        self._branding_card = ctk.CTkFrame(self._cards_container, fg_color=get_color("CARD_BG"), corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=get_color("BORDER"))
        self._branding_card.grid(row=3, column=0, columnspan=2, pady=(0, 20), sticky="ew")
        self._branding_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self._branding_card, text="Branding Consistency Engine", font=get_font_h3(), text_color=get_color("TEXT_PRIMARY")).grid(row=0, column=0, columnspan=2, padx=24, pady=(20, 12), sticky="w")

        metrics = [
            ("brand_logos", "Loaded Logo Count:"),
            ("brand_names", "Loaded Logo Names:"),
            ("brand_fingerprint", "Fingerprint Generation:"),
            ("brand_status", "Engine Status:"),
            ("brand_total_matches", "Total Matches Performed:"),
            ("brand_success_rate", "Match Success Rate:"),
            ("brand_images_analyzed", "Total Images Analyzed:"),
            ("brand_mismatches", "Mismatches Detected:"),
            ("brand_duration", "Last Match Duration:")
        ]

        self._branding_labels = {}
        for idx, (key, label) in enumerate(metrics):
            ctk.CTkLabel(self._branding_card, text=label, font=get_font_body(), text_color=get_color("TEXT_SECONDARY")).grid(row=idx+1, column=0, padx=24, pady=6, sticky="nw")
            if key == "brand_names":
                val = ctk.CTkLabel(self._branding_card, text="N/A", font=get_font_caption(), text_color=get_color("TEXT_PRIMARY"), justify="right", wraplength=550)
            else:
                val = ctk.CTkLabel(self._branding_card, text="N/A", font=get_font_body("bold"), text_color=get_color("TEXT_PRIMARY"))
            val.grid(row=idx+1, column=1, padx=24, pady=6, sticky="ne")
            self._branding_labels[key] = val

    def _build_collapsible_section(self) -> None:
        self._adv_container = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._adv_container.grid(row=4, column=0, padx=32, pady=(0, 32), sticky="ew")
        self._adv_container.grid_columnconfigure(0, weight=1)

        self._btn_toggle = ctk.CTkButton(
            self._adv_container, text="▼ Show Advanced Diagnostics", font=get_font_body("bold"),
            height=40, corner_radius=8, fg_color=get_color("ROW_BG"), hover_color=get_color("BORDER"),
            text_color=get_color("TEXT_PRIMARY"), command=self._toggle_advanced
        )
        self._btn_toggle.grid(row=0, column=0, sticky="ew")

        # Hidden advanced frame
        self._adv_frame = ctk.CTkFrame(self._adv_container, fg_color=get_color("CARD_BG"), corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=get_color("BORDER"))
        self._adv_frame.grid(row=1, column=0, pady=(12, 0), sticky="ew")
        self._adv_frame.grid_columnconfigure(0, weight=1)
        self._adv_frame.grid_remove()  # Collapsed by default

        # Inside advanced frame: Scrollable text boxes for rejections, logs, traces
        def create_trace_box(parent, title, row_idx):
            ctk.CTkLabel(parent, text=title, font=get_font_h3(), text_color=get_color("TEXT_PRIMARY")).grid(row=row_idx*2, column=0, padx=24, pady=(16, 6), sticky="w")
            box = ctk.CTkTextbox(parent, height=150, font=("Courier New", 11), fg_color=get_color("APP_BG"), border_width=1, border_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"))
            box.grid(row=row_idx*2+1, column=0, padx=24, pady=(0, 16), sticky="ew")
            return box

        self._box_rejections = create_trace_box(self._adv_frame, "Match Rejections List", 0)
        self._box_logs = create_trace_box(self._adv_frame, "Candidate Comparison Logs", 1)
        self._box_debug = create_trace_box(self._adv_frame, "Debug Traces Output", 2)

    # ─── Callbacks & Logic ────────────────────────────────────────────────────

    def on_show(self) -> None:
        self._refresh_all()

    def _toggle_advanced(self) -> None:
        self._adv_expanded = not self._adv_expanded
        if self._adv_expanded:
            self._btn_toggle.configure(text="▲ Hide Advanced Diagnostics")
            self._adv_frame.grid()
            self._populate_advanced_diagnostics()
        else:
            self._btn_toggle.configure(text="▼ Show Advanced Diagnostics")
            self._adv_frame.grid_remove()

    def _refresh_all(self) -> None:
        # Load rule stats
        loader = self._loader
        
        self._kb_health_labels["kb_loaded"].configure(text=str(len(loader.vulnerabilities)))
        self._kb_health_labels["kb_duplicates_id"].configure(text=str(loader.duplicate_ids_count))
        self._kb_health_labels["kb_duplicates_title"].configure(text=str(loader.duplicate_titles_count))
        self._kb_health_labels["kb_missing_kws"].configure(text=str(loader.missing_keywords_count))
        self._kb_health_labels["kb_missing_desc"].configure(text=str(loader.missing_descriptions_count))
        self._kb_health_labels["kb_missing_rem"].configure(text=str(loader.missing_remediations_count))
        self._kb_health_labels["kb_status"].configure(text=str(len(loader.diagnostics_warnings)))

        # Load performance metrics from last_scan_performance.json
        perf_path = os.path.join(get_data_path(), "last_scan_performance.json")
        perf_data = {}
        if os.path.exists(perf_path):
            try:
                with open(perf_path, "r", encoding="utf-8") as f:
                    perf_data = json.load(f)
            except Exception:
                pass

        self._perf_labels["perf_parse"].configure(text=f"{perf_data.get('pdf_parse_time_ms', 0.0):.1f} ms")
        self._perf_labels["perf_load"].configure(text=f"{perf_data.get('rule_load_time_ms', 0.0):.1f} ms")
        self._perf_labels["perf_match"].configure(text=f"{perf_data.get('match_engine_time_ms', 0.0):.1f} ms")
        self._perf_labels["perf_export"].configure(text=f"{perf_data.get('report_export_time_ms', 0.0):.1f} ms")
        self._perf_labels["perf_total"].configure(text=f"{perf_data.get('total_scan_time_ms', 0.0):.1f} ms")

        # Load navigation performance from main_window
        mw = self._main_window
        self._perf_labels["nav_last"].configure(text=f"{mw.last_switch_ms:.1f} ms")
        self._perf_labels["nav_avg"].configure(text=f"{mw.average_switch_ms:.1f} ms")
        self._perf_labels["nav_worst"].configure(text=f"{mw.worst_switch_ms:.1f} ms")


        path_checks = [
            ("path_rules", get_rules_path(""), False),
            ("path_data", get_data_path(""), False),
            ("path_reports", get_reports_path(""), False),
            ("path_exports", get_exports_path(""), False),
            ("path_logos", get_logo_repository_path(""), False),
            ("path_assets", get_assets_path(""), False),
            ("path_learning", get_rules_path("learning_queue.json"), True),
            ("path_manifest", get_data_path("runtime_manifest.json"), True)
        ]
        
        for key, path_val, is_file in path_checks:
            try:
                exists = os.path.exists(path_val)
                status_str = "✓ Available" if exists else "✗ Missing"
                color = get_color("SUCCESS") if exists else get_color("CRITICAL")
                self._storage_labels[key].configure(
                    text=f"{status_str}\n{path_val}",
                    text_color=color
                )
            except Exception as e:
                self._storage_labels[key].configure(
                    text=f"✗ Error\n{e}",
                    text_color=get_color("CRITICAL")
                )

        # RulesLoader Verification counters
        self._storage_labels["loader_rules_reload"].configure(text=str(loader.rules_reload_count))
        self._storage_labels["loader_kb_reload"].configure(text=str(loader.kb_reload_count))
        self._storage_labels["loader_last_time"].configure(text=str(loader.last_reload_time))

        # Match Engine Stats (from last_scan_diagnostics.json)
        diag_path = os.path.join(get_data_path(), "last_scan_diagnostics.json")
        diag_data = {}
        if os.path.exists(diag_path):
            try:
                with open(diag_path, "r", encoding="utf-8") as f:
                    diag_data = json.load(f)
            except Exception:
                pass

        matched_c = diag_data.get("matched_count", 0)
        unmatched_c = diag_data.get("unmatched_count", 0)
        total_c = matched_c + unmatched_c
        self._match_stats_labels["scan_findings"].configure(text=str(total_c))
        self._match_stats_labels["scan_matched"].configure(text=str(matched_c))
        self._match_stats_labels["scan_unmatched"].configure(text=str(unmatched_c))

        # Count qualities from diagnostics if saved
        ex_c = diag_data.get("excellent_count", 0)
        st_c = diag_data.get("strong_count", 0)
        pt_c = diag_data.get("partial_count", 0)

        # Get average match confidence from scan history
        avg_mq = 0.0
        hist_path = os.path.join(get_data_path(), "scan_history.json")
        if os.path.exists(hist_path):
            try:
                with open(hist_path, "r", encoding="utf-8") as f:
                    scan_history = json.load(f)
                    if scan_history:
                        last_scan = scan_history[0]
                        avg_mq = last_scan.get("avg_match_quality", 0.0)
            except Exception:
                pass

        self._match_stats_labels["scan_avg_quality"].configure(text=f"{avg_mq:.1f}%" if avg_mq > 0 else "N/A")
        self._match_stats_labels["scan_excellent"].configure(text=str(ex_c))
        self._match_stats_labels["scan_strong"].configure(text=str(st_c))
        self._match_stats_labels["scan_partial"].configure(text=str(pt_c))

        # ─── Refresh Application Health Card ─────────────────────────────────
        self._refresh_health_card(loader, perf_data)
        
        # ─── Refresh Branding consistency Card ──────────────────────────────
        self._refresh_branding_card()

    def _refresh_branding_card(self) -> None:
        try:
            from app.services.branding_engine import BrandingEngine
            engine = BrandingEngine()
            
            self._branding_labels["brand_logos"].configure(text=str(engine.loaded_logos_count))
            self._branding_labels["brand_names"].configure(
                text=", ".join(engine.loaded_logos_names) if engine.loaded_logos_names else "None"
            )
            self._branding_labels["brand_fingerprint"].configure(text=engine.fingerprint_status)
            
            # Status colors
            status_color = get_color("SUCCESS") if engine.status == "Operational" else get_color("WARNING") if engine.status == "Initializing" else get_color("CRITICAL")
            self._branding_labels["brand_status"].configure(text=engine.status, text_color=status_color)
            
            self._branding_labels["brand_total_matches"].configure(text=str(engine.total_matches_performed))
            
            rate = (engine.match_success_count / engine.total_matches_performed * 100.0) if engine.total_matches_performed > 0 else 0.0
            self._branding_labels["brand_success_rate"].configure(text=f"{rate:.1f}%")
            
            self._branding_labels["brand_images_analyzed"].configure(text=str(engine.total_images_analyzed))
            self._branding_labels["brand_mismatches"].configure(text=str(engine.total_mismatches_found))
            self._branding_labels["brand_duration"].configure(text=f"{engine.last_matching_duration_ms:.1f} ms")
        except Exception:
            pass

    def _refresh_health_card(self, loader: RulesLoader, perf_data: dict) -> None:
        # 1. KB Integrity
        kb_ok = len(loader.diagnostics_warnings) == 0
        self._health_labels["kb"].set_state("Compliant" if kb_ok else "Warning")

        # 2. Storage Paths
        rules_dir = get_rules_path("")
        paths_ok = os.path.exists(rules_dir) and os.path.exists(os.path.join(rules_dir, "vulnerabilities.json"))
        self._health_labels["storage"].set_state("Compliant" if paths_ok else "Failed")

        # 3. Report Storage
        rep_dir = get_reports_path()
        rep_ok = os.path.exists(rep_dir) and os.access(rep_dir, os.W_OK)
        self._health_labels["reports"].set_state("Compliant" if rep_ok else "Failed")

        # 4. Match Engine
        # Engine is OK if vulnerabilities are loaded and matcher is ready
        engine_ok = len(loader.vulnerabilities) > 0
        self._health_labels["engine"].set_state("Compliant" if engine_ok else "Warning")

        # 5. Performance
        # Performance is OK if average switch time < 250ms
        perf_ok = self._main_window.average_switch_ms < 250.0
        self._health_labels["perf"].set_state("Compliant" if perf_ok else "Warning")

        # Overall Status
        if not paths_ok or not rep_ok:
            self._overall_status_lbl.configure(text="Error (Critical Paths Missing)", text_color=get_color("CRITICAL"))
        elif not kb_ok or not engine_ok or not perf_ok:
            self._overall_status_lbl.configure(text="Warning (Issues Detected)", text_color=get_color("WARNING"))
        else:
            self._overall_status_lbl.configure(text="Healthy", text_color=get_color("SUCCESS"))

    def _populate_advanced_diagnostics(self) -> None:
        diag_path = os.path.join(get_data_path(), "last_scan_diagnostics.json")
        diag_data = {}
        if os.path.exists(diag_path):
            try:
                with open(diag_path, "r", encoding="utf-8") as f:
                    diag_data = json.load(f)
            except Exception:
                pass

        # Populate Rejections
        rejections = diag_data.get("rejections", [])
        self._box_rejections.delete("1.0", "end")
        if rejections:
            self._box_rejections.insert("1.0", "\n".join(rejections))
        else:
            self._box_rejections.insert("1.0", "No rejections found in last scan.")

        # Populate Logs
        logs = diag_data.get("comparison_logs", [])
        self._box_logs.delete("1.0", "end")
        if logs:
            self._box_logs.insert("1.0", "\n".join(logs))
        else:
            self._box_logs.insert("1.0", "No comparison logs recorded.")

        # Populate Debug traces
        debug = diag_data.get("debug_output", [])
        self._box_debug.delete("1.0", "end")
        if debug:
            self._box_debug.insert("1.0", "\n".join(debug))
        else:
            self._box_debug.insert("1.0", "No debug output traces found.")
