"""
rules_page.py — Rules Management page.
Phase 5D: Professional Vulnerability KB editor, structured Validators,
           dataset entry counts, search on list tabs.
"""
from __future__ import annotations
import json
import os
import shutil
import datetime
import glob
import uuid
import customtkinter as ctk
from typing import Any, Dict, List, Optional

from app.services.rules_loader import RulesLoader
from app.utils.path_helper import get_rules_path, get_backups_dir
from app.utils.activity_helper import log_activity, increment_learning_stat
from app.ui.theme import (
    get_color, get_font_h1, get_font_h2, get_font_h3,
    get_font_body, get_font_caption, RADIUS, BORDER_WIDTH,
)
from app.ui.components import StatusBadge, CustomDialog

# ─── Severity colours ────────────────────────────────────────────────────────
SEVERITY_COLORS: Dict[str, str] = {
    "Critical":    "CRITICAL",
    "High":        "WARNING",
    "Medium":      "ACCENT",
    "Low":         "SUCCESS",
    "Information": "TEXT_SECONDARY",
}
SEVERITY_OPTIONS = ["Critical", "High", "Medium", "Low", "Information"]
PENALTY_OPTIONS  = ["Critical", "Warning", "Information"]


# ─── RulesPage ───────────────────────────────────────────────────────────────

class RulesPage(ctk.CTkFrame):
    def __init__(self, parent, main_window, **kwargs):
        print("Rules Page Created")
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._main_window = main_window
        self._loader = RulesLoader()

        self._search_vars: dict[str, ctk.StringVar] = {}

        # Vulnerability KB state
        self._vuln_data: List[Dict] = []
        self._selected_vuln_idx: Optional[int] = None
        self._vuln_search_var = ctk.StringVar()
        self._vuln_search_var.trace_add("write", lambda *_: self._populate_vuln_list())

        # Validators JSON-advanced toggle
        self._validators_json_visible = False

        # Lazy loading states
        self._loaded_tabs = set()
        self._last_rules_reload = -1
        self._last_kb_reload = -1

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.grid(row=0, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        self._build()

    # ═══════════════════════════════════════════════════════════════════════
    # BUILD
    # ═══════════════════════════════════════════════════════════════════════

    def _build(self) -> None:
        S = self._scroll

        # Header
        hdr = ctk.CTkFrame(S, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=32, pady=(28, 24), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(hdr, text="Rules Engine", font=get_font_h1(),
                     text_color=get_color("TEXT_PRIMARY")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(hdr, text="Manage knowledge bases and compliance logic datasets.",
                     font=get_font_body(), text_color=get_color("TEXT_SECONDARY")).grid(
            row=1, column=0, sticky="w", pady=(4, 0))

        btn_box = ctk.CTkFrame(hdr, fg_color="transparent")
        btn_box.grid(row=0, column=1, rowspan=2, sticky="e")

        ctk.CTkButton(
            btn_box, text="🔄 Reload Rules", height=36, corner_radius=8,
            font=get_font_body("bold"), fg_color=get_color("ROW_BG"),
            hover_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"),
            command=self._cmd_reload_rules,
        ).pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            btn_box, text="💾 Backup All", height=36, corner_radius=8,
            font=get_font_body("bold"), fg_color=get_color("ACCENT"),
            hover_color=get_color("BORDER"),
            command=self._cmd_backup_all,
        ).pack(side="left")

        # Main Tabview
        self._tabview = ctk.CTkTabview(
            S,
            fg_color=get_color("CARD_BG"),
            corner_radius=RADIUS,
            border_width=BORDER_WIDTH,
            border_color=get_color("BORDER"),
            segmented_button_fg_color=get_color("ROW_BG"),
            segmented_button_selected_color=get_color("ACCENT"),
            segmented_button_selected_hover_color=get_color("BORDER"),
            segmented_button_unselected_color=get_color("ROW_BG"),
            segmented_button_unselected_hover_color=get_color("BORDER"),
            text_color=get_color("TEXT_PRIMARY"),
            command=self._on_tab_changed,
        )
        self._tabview.grid(row=1, column=0, padx=32, pady=(0, 32), sticky="nsew")

        tabs = [
            ("diagnostics",       "Diagnostics"),
            ("learning_queue",    "Learning Queue"),
            ("whitelist",         "Whitelist"),
            ("organization_terms","Organization Terms"),
            ("organization_logos","Organization Logos"),
            ("required_sections", "Sections"),
            ("acronyms",          "Acronyms"),
            ("custom_rules",      "Validators"),
            ("vulnerabilities",   "Vulnerability KB"),
        ]

        self._tab_frames: dict[str, ctk.CTkFrame] = {}
        for k, title in tabs:
            t = self._tabview.add(title)
            t.grid_columnconfigure(0, weight=1)
            t.grid_rowconfigure(1, weight=1)
            self._tab_frames[k] = t

        self._build_diagnostics_tab()
        self._build_learning_queue_tab()
        self._build_organization_logos_tab()
        self._build_tab_list("whitelist",
                             "Allowed terms that won't trigger spelling alerts.",
                             "Add Whitelist Entry")
        self._build_tab_list("required_sections",
                             "Exact heading names that must be present in the document.",
                             "Add Heading Name (e.g., '1.0 Introduction')")
        self._build_tab_dict("acronyms",
                             "Key-value pairs of Acronyms and their expected definitions.",
                             "Acronym (e.g., 'NASA')", "Definition")
        self._build_tab_list("organization_terms",
                             "Approved organizational terminology.",
                             "Add Term (e.g., 'Acme Corp')")
        self._build_validators_tab()
        self._build_vuln_kb_tab()

        self._refresh_diagnostics()

    # ─── Diagnostics tab ────────────────────────────────────────────────────

    def _build_diagnostics_tab(self):
        parent = self._tab_frames["diagnostics"]
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        # Container frame
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.grid(row=0, column=0, sticky="nsew", padx=24, pady=20)
        container.grid_columnconfigure(0, weight=1)

        # Header Frame
        d_hdr = ctk.CTkFrame(container, fg_color="transparent")
        d_hdr.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        d_hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(d_hdr, text="Knowledge Base Diagnostics & System Inventory",
                     font=get_font_h3(), text_color=get_color("TEXT_PRIMARY")).grid(
             row=0, column=0, sticky="w")
        StatusBadge(d_hdr, state="Active").grid(row=0, column=1, sticky="e")

        # 1. Knowledge Sources Frame
        ks_frame = ctk.CTkFrame(container, fg_color=get_color("CARD_BG"), corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=get_color("BORDER"))
        ks_frame.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        ks_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(ks_frame, text="Knowledge Sources", font=get_font_h3(), text_color=get_color("TEXT_PRIMARY")).grid(row=0, column=0, padx=20, pady=(16, 12), sticky="w")

        # Table container
        self._ks_table = ctk.CTkFrame(ks_frame, fg_color="transparent")
        self._ks_table.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
        
        # 3-Column Bottom Grid for Branding, Validation, Learning Resources
        bottom_grid = ctk.CTkFrame(container, fg_color="transparent")
        bottom_grid.grid(row=2, column=0, sticky="ew")
        bottom_grid.grid_columnconfigure((0, 1, 2), weight=1)

        # 2. Branding Resources Frame
        br_frame = ctk.CTkFrame(bottom_grid, fg_color=get_color("CARD_BG"), corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=get_color("BORDER"))
        br_frame.grid(row=0, column=0, padx=(0, 8), sticky="nsew")
        br_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(br_frame, text="Branding Resources", font=get_font_h3(), text_color=get_color("TEXT_PRIMARY")).grid(row=0, column=0, padx=20, pady=(16, 12), sticky="w")
        self._br_content = ctk.CTkFrame(br_frame, fg_color="transparent")
        self._br_content.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")

        # 3. Validation Resources Frame
        vr_frame = ctk.CTkFrame(bottom_grid, fg_color=get_color("CARD_BG"), corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=get_color("BORDER"))
        vr_frame.grid(row=0, column=1, padx=8, sticky="nsew")
        vr_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(vr_frame, text="Validation Resources", font=get_font_h3(), text_color=get_color("TEXT_PRIMARY")).grid(row=0, column=0, padx=20, pady=(16, 12), sticky="w")
        self._vr_content = ctk.CTkFrame(vr_frame, fg_color="transparent")
        self._vr_content.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")

        # 4. Learning Resources Frame
        lr_frame = ctk.CTkFrame(bottom_grid, fg_color=get_color("CARD_BG"), corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=get_color("BORDER"))
        lr_frame.grid(row=0, column=2, padx=(8, 0), sticky="nsew")
        lr_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(lr_frame, text="Learning Resources", font=get_font_h3(), text_color=get_color("TEXT_PRIMARY")).grid(row=0, column=0, padx=20, pady=(16, 12), sticky="w")
        self._lr_content = ctk.CTkFrame(lr_frame, fg_color="transparent")
        self._lr_content.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")

    # ─── Generic list tab (Whitelist, Required Sections) ───────────────────

    def _build_tab_list(self, key: str, desc: str, placeholder: str):
        parent = self._tab_frames[key]
        parent.grid_rowconfigure(2, weight=1)

        # Header row with description, count, and search
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=24, pady=(12, 8))
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top, text=desc, font=get_font_body(),
                     text_color=get_color("TEXT_SECONDARY")).grid(row=0, column=0, sticky="w")

        cnt_lbl = ctk.CTkLabel(top, text="0 entries", font=get_font_caption("bold"),
                               text_color=get_color("ACCENT"))
        cnt_lbl.grid(row=0, column=1, sticky="e", padx=(8, 12))
        setattr(self, f"_cnt_{key}", cnt_lbl)

        svar = ctk.StringVar()
        self._search_vars[key] = svar
        search = ctk.CTkEntry(top, placeholder_text="🔍 Search...", textvariable=svar,
                              width=180, height=30, font=get_font_body(), corner_radius=6,
                              fg_color=get_color("ROW_BG"), border_color=get_color("BORDER"),
                              text_color=get_color("TEXT_PRIMARY"))
        search.grid(row=0, column=2, sticky="e")
        svar.trace_add("write", lambda *a, k=key: self._populate_list(k))

        sf = ctk.CTkScrollableFrame(parent, fg_color=get_color("APP_BG"), height=340,
                                    corner_radius=8, border_width=1,
                                    border_color=get_color("BORDER"))
        sf.grid(row=1, column=0, sticky="nsew", pady=(0, 12), padx=24)
        sf.grid_columnconfigure(0, weight=1)
        setattr(self, f"_sf_{key}", sf)

        add_frame = ctk.CTkFrame(parent, fg_color="transparent")
        add_frame.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 24))
        add_frame.grid_columnconfigure(0, weight=1)

        entry = ctk.CTkEntry(add_frame, placeholder_text=placeholder, font=get_font_body(),
                             height=36, corner_radius=6, fg_color=get_color("ROW_BG"),
                             border_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"))
        entry.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        entry.bind("<Return>", lambda _: self._cmd_add_list(key, entry))

        ctk.CTkButton(
            add_frame, text="＋ Add Entry", font=get_font_body("bold"), height=36,
            corner_radius=6, fg_color=get_color("ACCENT"), hover_color=get_color("BORDER"),
            command=lambda: self._cmd_add_list(key, entry),
        ).grid(row=0, column=1)

    # ─── Generic dict tab (Acronyms, Organization Terms) ───────────────────

    def _build_tab_dict(self, key: str, desc: str, p1: str, p2: str):
        parent = self._tab_frames[key]
        parent.grid_rowconfigure(2, weight=1)

        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", pady=(12, 8), padx=24)
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(hdr, text=desc, font=get_font_body(),
                     text_color=get_color("TEXT_SECONDARY")).grid(row=0, column=0, sticky="w")

        cnt_lbl = ctk.CTkLabel(hdr, text="0 entries", font=get_font_caption("bold"),
                               text_color=get_color("ACCENT"))
        cnt_lbl.grid(row=0, column=1, sticky="e", padx=(8, 12))
        setattr(self, f"_cnt_{key}", cnt_lbl)

        svar = ctk.StringVar()
        self._search_vars[key] = svar
        search = ctk.CTkEntry(hdr, placeholder_text="🔍 Search...", textvariable=svar,
                              width=200, height=30, font=get_font_body(), corner_radius=6,
                              fg_color=get_color("ROW_BG"), border_color=get_color("BORDER"),
                              text_color=get_color("TEXT_PRIMARY"))
        search.grid(row=0, column=2, sticky="e")
        svar.trace_add("write", lambda *a, k=key: self._populate_dict(k))

        sf = ctk.CTkScrollableFrame(parent, fg_color=get_color("APP_BG"), height=340,
                                    corner_radius=8, border_width=1,
                                    border_color=get_color("BORDER"))
        sf.grid(row=1, column=0, sticky="nsew", pady=(0, 12), padx=24)
        sf.grid_columnconfigure((0, 1), weight=1)
        setattr(self, f"_sf_{key}", sf)

        add_frame = ctk.CTkFrame(parent, fg_color="transparent")
        add_frame.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 24))
        add_frame.grid_columnconfigure((0, 1), weight=1)

        e1 = ctk.CTkEntry(add_frame, placeholder_text=p1, font=get_font_body(), height=36,
                          corner_radius=6, fg_color=get_color("ROW_BG"),
                          border_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"))
        e1.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        e2 = ctk.CTkEntry(add_frame, placeholder_text=p2, font=get_font_body(), height=36,
                          corner_radius=6, fg_color=get_color("ROW_BG"),
                          border_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"))
        e2.grid(row=0, column=1, sticky="ew", padx=(0, 12))

        ctk.CTkButton(
            add_frame, text="＋ Add Pair", font=get_font_body("bold"), height=36,
            corner_radius=6, fg_color=get_color("ACCENT"), hover_color=get_color("BORDER"),
            command=lambda: self._cmd_add_dict(key, e1, e2),
        ).grid(row=0, column=2)


    # ─── Learning Queue tab ──────────────────────────────────────────────────

    def _build_learning_queue_tab(self):
        parent = self._tab_frames["learning_queue"]
        parent.grid_rowconfigure(1, weight=1)

        top_bar = ctk.CTkFrame(parent, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(12, 8))
        top_bar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top_bar, text="Review pending knowledge items submitted from scan reports.", font=get_font_body(), text_color=get_color("TEXT_SECONDARY")).grid(row=0, column=0, sticky="w")
        
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)
        scroll.grid_columnconfigure(0, weight=1)
        
        self._lq_container = scroll
        self._populate_learning_queue()

    def _populate_learning_queue(self):
        for w in self._lq_container.winfo_children(): w.destroy()
        queue = self._loader.learning_queue
        if not queue:
            ctk.CTkLabel(self._lq_container, text="The learning queue is empty.", font=get_font_body(), text_color=get_color("TEXT_MUTED"), wraplength=300, justify="left").pack(pady=40)
            return
            
        for i, item in enumerate(queue):
            f = ctk.CTkFrame(self._lq_container, fg_color=get_color("APP_BG"), corner_radius=8, border_width=1, border_color=get_color("BORDER"))
            f.pack(fill="x", pady=6)
            f.grid_columnconfigure(1, weight=1)
            
            # Info
            info = ctk.CTkFrame(f, fg_color="transparent")
            info.grid(row=0, column=0, sticky="w", padx=16, pady=12)
            
            term = item.get("term", "")
            typ = item.get("type", "Term")
            count = item.get("count", 0)
            src = item.get("source_doc", "Unknown")
            
            ctk.CTkLabel(info, text=term, font=get_font_h3(), text_color=get_color("TEXT_PRIMARY")).pack(anchor="w")
            ctk.CTkLabel(info, text=f"{typ} • Found {count} times • Source: {src}", font=get_font_caption(), text_color=get_color("TEXT_SECONDARY")).pack(anchor="w", pady=(2,0))
            
            # Actions
            acts = ctk.CTkFrame(f, fg_color="transparent")
            acts.grid(row=0, column=2, sticky="e", padx=16, pady=12)
            
            def approve(t=term, ty=typ, it=item):
                if ty == "Organization":
                    orgs = list(self._loader.organization_terms)
                    orgs.append(t)
                    self._loader.save_organization_terms(orgs)
                elif ty == "Acronym":
                    acrs = dict(self._loader._acronyms)
                    acrs[t.upper()] = "Approved via Queue"
                    self._loader.save_acronyms(acrs)
                else:
                    wl = list(self._loader.whitelist)
                    wl.append(t)
                    self._loader.save_whitelist(wl)
                q = [x for x in self._loader.learning_queue if x != it]
                self._loader.save_learning_queue(q)
                log_activity(f"Approved candidate: {t}", "Discovery Approved", t)
                increment_learning_stat("approved")
                self._populate_learning_queue()
                
            def reject(it=item):
                q = [x for x in self._loader.learning_queue if x != it]
                self._loader.save_learning_queue(q)
                log_activity(f"Rejected candidate: {it.get('term', '')}", "Discovery Rejected", it.get('term', ''))
                increment_learning_stat("rejected")
                self._populate_learning_queue()
            
            ctk.CTkButton(acts, text="Approve", width=80, fg_color=get_color("SUCCESS"), hover_color=get_color("BORDER"), command=approve).pack(side="left", padx=(0, 8))
            ctk.CTkButton(acts, text="Reject", width=80, fg_color=get_color("CRITICAL"), hover_color=get_color("BORDER"), command=reject).pack(side="left")

    # ─── Organization Logos tab ──────────────────────────────────────────────

    def _build_organization_logos_tab(self):
        parent = self._tab_frames["organization_logos"]
        parent.grid_rowconfigure(1, weight=1)

        top_bar = ctk.CTkFrame(parent, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(12, 8))
        top_bar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top_bar, text="Manage valid organization logos for branding validation.", font=get_font_body(), text_color=get_color("TEXT_SECONDARY")).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(top_bar, text="Upload Logo", fg_color=get_color("ACCENT"), hover_color=get_color("BORDER"), command=self._upload_logo).grid(row=0, column=1, sticky="e")
        
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)
        scroll.grid_columnconfigure((0,1,2,3), weight=1)
        
        self._logos_container = scroll
        self._populate_logos()

    def _populate_logos(self):
        import os, datetime
        from PIL import Image
        from app.utils.path_helper import get_logo_repository_path
        for w in self._logos_container.winfo_children(): w.destroy()
        
        logo_dir = get_logo_repository_path()
        if not os.path.exists(logo_dir):
            os.makedirs(logo_dir, exist_ok=True)
            
        files = [f for f in os.listdir(logo_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        if not files:
            ctk.CTkLabel(self._logos_container, text="No logos found.", font=get_font_body(), text_color=get_color("TEXT_MUTED")).grid(row=0, column=0, pady=40, columnspan=4)
            return
            
        for i, f in enumerate(files):
            path = os.path.join(logo_dir, f)
            card = ctk.CTkFrame(self._logos_container, fg_color=get_color("APP_BG"), corner_radius=8, border_width=1, border_color=get_color("BORDER"))
            card.grid(row=i//4, column=i%4, padx=8, pady=8, sticky="nsew")
            
            try:
                img = Image.open(path)
                img.thumbnail((96, 96)) # Maintain aspect ratio max 96x96
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                lbl = ctk.CTkLabel(card, image=ctk_img, text="")
                lbl.pack(pady=(16, 8))
            except Exception:
                ctk.CTkLabel(card, text="Image Error", text_color="red").pack(pady=(16, 8))
                
            org_name = os.path.splitext(f)[0]
            ctk.CTkLabel(card, text=org_name, font=get_font_caption("bold"), text_color=get_color("TEXT_PRIMARY")).pack(pady=(0, 4))
            
            dt = datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d')
            ctk.CTkLabel(card, text=f"Added: {dt}", font=get_font_caption(), text_color=get_color("TEXT_MUTED")).pack(pady=(0, 12))
            
            def delete_logo(p=path):
                try:
                    os.remove(p)
                    log_activity(f"Logo deleted: {os.path.basename(p)}", "Knowledge Base Updated", os.path.basename(p))
                    self._populate_logos()
                except Exception as e:
                    print(e)
            
            ctk.CTkButton(card, text="Delete", fg_color="transparent", border_width=1, border_color=get_color("CRITICAL"), hover_color=get_color("CRITICAL"), text_color=get_color("TEXT_PRIMARY"), width=80, height=24, command=delete_logo).pack(pady=(0, 16))

    def _upload_logo(self):
        import os, shutil
        from tkinter import filedialog
        from app.utils.path_helper import get_logo_repository_path
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg")])
        if path:
            dest_dir = get_logo_repository_path()
            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, os.path.basename(path))
            try:
                shutil.copy(path, dest)
                log_activity(f"Logo uploaded: {os.path.basename(path)}", "Logo Added", os.path.basename(path))
                self._populate_logos()
            except Exception as e:
                print(e)


    # ─── Validators tab ─────────────────────────────────────────────────────

    def _build_validators_tab(self):
        parent = self._tab_frames["custom_rules"]
        parent.grid_rowconfigure(1, weight=1)

        top_bar = ctk.CTkFrame(parent, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(12, 8))
        top_bar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top_bar,
                     text="Toggle validators and set penalty severity. Changes save immediately.",
                     font=get_font_body(), text_color=get_color("TEXT_SECONDARY")).grid(
            row=0, column=0, sticky="w")

        self._btn_json_toggle = ctk.CTkButton(
            top_bar, text="{ } Advanced JSON", height=30, corner_radius=6,
            font=get_font_caption("bold"), fg_color=get_color("ROW_BG"),
            hover_color=get_color("BORDER"), text_color=get_color("TEXT_SECONDARY"),
            command=self._toggle_validators_json,
        )
        self._btn_json_toggle.grid(row=0, column=1, sticky="e")

        # Scrollable card list
        self._validators_sf = ctk.CTkScrollableFrame(
            parent, fg_color=get_color("APP_BG"), height=340,
            corner_radius=8, border_width=1, border_color=get_color("BORDER"),
        )
        self._validators_sf.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 8))
        self._validators_sf.grid_columnconfigure(0, weight=1)

        # JSON advanced editor (hidden by default)
        self._validators_json_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._validators_json_frame.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 24))
        self._validators_json_frame.grid_columnconfigure(0, weight=1)
        self._validators_json_frame.grid_remove()  # hidden

        json_top = ctk.CTkFrame(self._validators_json_frame, fg_color="transparent")
        json_top.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        json_top.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(json_top, text="Raw JSON Editor (Advanced)",
                     font=get_font_caption("bold"),
                     text_color=get_color("TEXT_SECONDARY")).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            json_top, text="💾 Save JSON", height=28, corner_radius=6,
            font=get_font_caption("bold"), fg_color=get_color("SUCCESS"),
            hover_color=get_color("BORDER"),
            command=lambda: self._cmd_save_raw_json("custom_rules"),
        ).grid(row=0, column=1, sticky="e")

        self._textbox_custom_rules = ctk.CTkTextbox(
            self._validators_json_frame, font=("Courier New", 12),
            fg_color=get_color("APP_BG"), border_width=1,
            border_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"),
            height=200,
        )
        self._textbox_custom_rules.grid(row=1, column=0, sticky="ew")

    def _toggle_validators_json(self):
        self._validators_json_visible = not self._validators_json_visible
        if self._validators_json_visible:
            self._validators_json_frame.grid()
            self._btn_json_toggle.configure(text="▲ Hide JSON",
                                            text_color=get_color("ACCENT"))
            self._populate_raw_json("custom_rules")
        else:
            self._validators_json_frame.grid_remove()
            self._btn_json_toggle.configure(text="{ } Advanced JSON",
                                            text_color=get_color("TEXT_SECONDARY"))

    # ─── Vulnerability KB tab ───────────────────────────────────────────────

    def _build_vuln_kb_tab(self):
        parent = self._tab_frames["vulnerabilities"]
        parent.grid_columnconfigure(0, weight=2)
        parent.grid_columnconfigure(1, weight=3)
        parent.grid_rowconfigure(1, weight=1)

        # ── Top toolbar ────────────────────────────────────────────────────
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(12, 8))
        toolbar.grid_columnconfigure(1, weight=1)

        self._vuln_count_lbl = ctk.CTkLabel(
            toolbar, text="0 vulnerabilities", font=get_font_caption("bold"),
            text_color=get_color("ACCENT"),
        )
        self._vuln_count_lbl.grid(row=0, column=0, sticky="w", padx=(0, 16))

        search_entry = ctk.CTkEntry(
            toolbar, placeholder_text="🔍 Search vulnerabilities...",
            textvariable=self._vuln_search_var,
            height=32, font=get_font_body(), corner_radius=6,
            fg_color=get_color("ROW_BG"), border_color=get_color("BORDER"),
            text_color=get_color("TEXT_PRIMARY"),
        )
        search_entry.grid(row=0, column=1, sticky="ew", padx=(0, 12))

        # Export/Import buttons
        btn_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        btn_frame.grid(row=0, column=2, sticky="e")

        ctk.CTkButton(
            btn_frame, text="📥 Import", height=32, corner_radius=6,
            font=get_font_caption("bold"), fg_color=get_color("ROW_BG"),
            hover_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"),
            command=self._cmd_vuln_import,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_frame, text="📤 Export", height=32, corner_radius=6,
            font=get_font_caption("bold"), fg_color=get_color("ROW_BG"),
            hover_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"),
            command=self._cmd_vuln_export,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_frame, text="＋ New", height=32, corner_radius=6,
            font=get_font_body("bold"), fg_color=get_color("ACCENT"),
            hover_color=get_color("BORDER"),
            command=self._cmd_vuln_new,
        ).pack(side="left")

        # ── Left panel: scrollable list ────────────────────────────────────
        left_panel = ctk.CTkFrame(parent, fg_color=get_color("APP_BG"),
                                  corner_radius=8, border_width=1,
                                  border_color=get_color("BORDER"))
        left_panel.grid(row=1, column=0, sticky="nsew", padx=(24, 8), pady=(0, 24))
        left_panel.grid_rowconfigure(0, weight=1)
        left_panel.grid_columnconfigure(0, weight=1)

        self._vuln_list_frame = ctk.CTkScrollableFrame(left_panel, fg_color="transparent")
        self._vuln_list_frame.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._vuln_list_frame.grid_columnconfigure(0, weight=1)

        # ── Right panel: detail form ───────────────────────────────────────
        right_panel = ctk.CTkFrame(parent, fg_color=get_color("CARD_BG"),
                                   corner_radius=8, border_width=1,
                                   border_color=get_color("BORDER"))
        right_panel.grid(row=1, column=1, sticky="nsew", padx=(8, 24), pady=(0, 24))
        right_panel.grid_columnconfigure(0, weight=1)

        form_scroll = ctk.CTkScrollableFrame(right_panel, fg_color="transparent")
        form_scroll.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        form_scroll.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(0, weight=1)

        def lbl(text):
            ctk.CTkLabel(form_scroll, text=text, font=get_font_caption("bold"),
                         text_color=get_color("TEXT_SECONDARY")).pack(anchor="w", pady=(8, 2))

        # Title
        lbl("Vulnerability Title")
        self._vuln_f_title = ctk.CTkEntry(
            form_scroll, placeholder_text="e.g. SQL Injection Risk",
            font=get_font_body(), height=36, corner_radius=6,
            fg_color=get_color("ROW_BG"), border_color=get_color("BORDER"),
            text_color=get_color("TEXT_PRIMARY"),
        )
        self._vuln_f_title.pack(fill="x")

        # Severity
        lbl("Risk Severity")
        self._vuln_f_severity = ctk.CTkOptionMenu(
            form_scroll, values=SEVERITY_OPTIONS,
            font=get_font_body(), fg_color=get_color("ROW_BG"),
            button_color=get_color("ROW_BG"), button_hover_color=get_color("BORDER"),
            text_color=get_color("TEXT_PRIMARY"), dropdown_fg_color=get_color("CARD_BG"),
            dropdown_text_color=get_color("TEXT_PRIMARY"),
        )
        self._vuln_f_severity.pack(fill="x")
        self._vuln_f_severity.set("Medium")

        # Keywords
        lbl("Detection Keywords (comma-separated)")
        self._vuln_f_keywords = ctk.CTkEntry(
            form_scroll, placeholder_text="e.g. sql, injection, database",
            font=get_font_body(), height=36, corner_radius=6,
            fg_color=get_color("ROW_BG"), border_color=get_color("BORDER"),
            text_color=get_color("TEXT_PRIMARY"),
        )
        self._vuln_f_keywords.pack(fill="x")

        # Description
        lbl("Description")
        self._vuln_f_desc = ctk.CTkTextbox(
            form_scroll, height=100, font=get_font_body(),
            fg_color=get_color("ROW_BG"), border_width=1,
            border_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"),
        )
        self._vuln_f_desc.pack(fill="x")

        # Remediation
        lbl("Remediation Plan")
        self._vuln_f_rem = ctk.CTkTextbox(
            form_scroll, height=100, font=get_font_body(),
            fg_color=get_color("ROW_BG"), border_width=1,
            border_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"),
        )
        self._vuln_f_rem.pack(fill="x", pady=(0, 8))

        # Action buttons
        action_row = ctk.CTkFrame(right_panel, fg_color="transparent")
        action_row.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 16))

        ctk.CTkButton(
            action_row, text="💾 Save Vulnerability", font=get_font_body("bold"),
            height=36, corner_radius=6, fg_color=get_color("SUCCESS"),
            hover_color=get_color("BORDER"),
            command=self._cmd_vuln_save,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            action_row, text="＋ New", font=get_font_body("bold"),
            height=36, corner_radius=6, fg_color=get_color("ACCENT"),
            hover_color=get_color("BORDER"),
            command=self._cmd_vuln_new,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            action_row, text="🗑 Delete", font=get_font_body("bold"),
            height=36, corner_radius=6, fg_color=get_color("ROW_BG"),
            hover_color=get_color("CRITICAL"), text_color=get_color("TEXT_PRIMARY"),
            command=self._cmd_vuln_delete,
        ).pack(side="right")

    # ═══════════════════════════════════════════════════════════════════════
    # ON SHOW / REFRESH
    # ═══════════════════════════════════════════════════════════════════════

    def _on_tab_changed(self):
        tab_name = self._tabview.get()
        tab_map = {
            "Diagnostics": "diagnostics",
            "Learning Queue": "learning_queue",
            "Whitelist": "whitelist",
            "Organization Terms": "organization_terms",
            "Sections": "required_sections",
            "Acronyms": "acronyms",
            "Validators": "custom_rules",
            "Vulnerability KB": "vulnerabilities"
        }
        tab_key = tab_map.get(tab_name)
        if not tab_key:
            return

        if tab_key == "diagnostics":
            self._refresh_diagnostics()
            return

        if tab_key == "learning_queue":
            self._populate_learning_queue()
            return

        if tab_key in self._loaded_tabs:
            return

        self._loaded_tabs.add(tab_key)

        if tab_key == "whitelist":
            self._populate_list("whitelist")
        elif tab_key == "organization_terms":
            self._populate_list("organization_terms")
        elif tab_key == "required_sections":
            self._populate_list("required_sections")
        elif tab_key == "acronyms":
            self._populate_dict("acronyms")
        elif tab_key == "custom_rules":
            self._populate_validators()
        elif tab_key == "vulnerabilities":
            self._load_vuln_data()

    def on_show(self) -> None:
        loader = RulesLoader()
        if (loader.rules_reload_count != self._last_rules_reload or
            loader.kb_reload_count != self._last_kb_reload):
            self._last_rules_reload = loader.rules_reload_count
            self._last_kb_reload = loader.kb_reload_count
            self._loaded_tabs.clear()
        self._on_tab_changed()

    def _refresh_all(self):
        self._loaded_tabs.clear()
        self._on_tab_changed()

    def _refresh_diagnostics(self):
        for w in self._ks_table.winfo_children():
            w.destroy()
        for w in self._br_content.winfo_children():
            w.destroy()
        for w in self._vr_content.winfo_children():
            w.destroy()
        for w in self._lr_content.winfo_children():
            w.destroy()

        def format_size(size_bytes: int) -> str:
            if size_bytes <= 0:
                return "N/A"
            if size_bytes < 1024:
                return f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.1f} KB"
            else:
                return f"{size_bytes / (1024 * 1024):.1f} MB"

        headers = ["Name", "Status", "Entry Count", "Last Modified", "File Size"]
        for col_idx, h in enumerate(headers):
            lbl = ctk.CTkLabel(self._ks_table, text=h, font=get_font_caption("bold"), text_color=get_color("TEXT_SECONDARY"))
            lbl.grid(row=0, column=col_idx, padx=12, pady=6, sticky="w")

        self._ks_table.grid_columnconfigure(0, weight=2)
        self._ks_table.grid_columnconfigure(1, weight=1)
        self._ks_table.grid_columnconfigure(2, weight=1)
        self._ks_table.grid_columnconfigure(3, weight=2)
        self._ks_table.grid_columnconfigure(4, weight=1)

        sources = [
            ("Dictionary", "standard_english.json", len(self._loader.standard_english)),
            ("Cybersecurity Terms", "cybersecurity_terms.json", len(self._loader.cybersecurity_terms)),
            ("Acronyms", "acronyms.json", len(self._loader.acronyms)),
            ("Organization Terms", "organization_terms.json", len(self._loader.organization_terms)),
            ("Vulnerability KB", "vulnerabilities.json", len(self._loader.vulnerabilities)),
            ("Learning Queue", "learning_queue.json", len(self._loader.learning_queue))
        ]

        for row_idx, (name, filename, entry_count) in enumerate(sources):
            meta = self._loader.get_source_file_metadata(filename)
            status = meta.get("status", "Loaded")
            size_bytes = meta.get("size_bytes", 0)
            last_mod = meta.get("last_modified", "N/A")
            size_str = format_size(size_bytes)

            row_data = [name, status, f"{entry_count} entries", last_mod, size_str]
            for col_idx, val in enumerate(row_data):
                color = get_color("TEXT_PRIMARY")
                if col_idx == 1:
                    if status == "Loaded":
                        color = get_color("SUCCESS")
                    elif status == "Missing":
                        color = get_color("TEXT_SECONDARY")
                    else:
                        color = get_color("CRITICAL")
                
                lbl = ctk.CTkLabel(self._ks_table, text=str(val), font=get_font_body(), text_color=color)
                lbl.grid(row=row_idx + 1, column=col_idx, padx=12, pady=6, sticky="w")

        logos_meta = self._loader.get_logo_repository_metadata()
        logo_status = logos_meta.get("status", "Loaded")
        logo_count = logos_meta.get("count", 0)
        logo_size = format_size(logos_meta.get("size_bytes", 0))
        logo_mod = logos_meta.get("last_modified", "N/A")

        def add_detail_row(parent, row, label, value, val_color=get_color("TEXT_PRIMARY")):
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.grid(row=row, column=0, sticky="ew", pady=4)
            f.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(f, text=label, font=get_font_caption(), text_color=get_color("TEXT_SECONDARY")).pack(side="left")
            ctk.CTkLabel(f, text=value, font=get_font_body("bold"), text_color=val_color).pack(side="right")

        self._br_content.grid_columnconfigure(0, weight=1)
        add_detail_row(self._br_content, 0, "Repository Status:", logo_status, get_color("SUCCESS") if logo_status == "Loaded" else get_color("CRITICAL"))
        add_detail_row(self._br_content, 1, "Registered Logos:", f"{logo_count} logos")
        add_detail_row(self._br_content, 2, "Repository Size:", logo_size)
        add_detail_row(self._br_content, 3, "Last Modified:", logo_mod)

        active_validators = 0
        total_validators = 0
        for key in ["required_section_validation", "date_validation", "vulnerability_validation", "terminology_validation", "spelling_validation", "empty_page_validation", "serial_number_validation", "page_number_validation", "branding_validation"]:
            total_validators += 1
            rule = self._loader.custom_rules.get(key, {})
            default_val = False if key == "page_number_validation" else True
            if rule.get("enabled", default_val):
                active_validators += 1

        self._vr_content.grid_columnconfigure(0, weight=1)
        add_detail_row(self._vr_content, 0, "Active Validators:", f"{active_validators} active")
        add_detail_row(self._vr_content, 1, "Inactive Validators:", f"{total_validators - active_validators} inactive")
        add_detail_row(self._vr_content, 2, "Total Custom Rules:", f"{len(self._loader.custom_rules)} rules")
        add_detail_row(self._vr_content, 3, "Rules Status:", "Active", get_color("SUCCESS"))

        from app.utils.activity_helper import get_learning_stats
        l_stats = get_learning_stats()
        pending_count = len(self._loader.learning_queue)
        approved_count = l_stats.get("approved_count", 0)
        rejected_count = l_stats.get("rejected_count", 0)

        self._lr_content.grid_columnconfigure(0, weight=1)
        add_detail_row(self._lr_content, 0, "Pending Queue Items:", f"{pending_count} pending", get_color("WARNING") if pending_count > 0 else get_color("TEXT_SECONDARY"))
        add_detail_row(self._lr_content, 1, "Approved Discoveries:", f"{approved_count} approved", get_color("SUCCESS"))
        add_detail_row(self._lr_content, 2, "Rejected Discoveries:", f"{rejected_count} rejected", get_color("CRITICAL"))
        add_detail_row(self._lr_content, 3, "Queue State:", "Monitoring", get_color("ACCENT"))


    # ─── List / Dict populate ───────────────────────────────────────────────

    def _populate_list(self, key: str):
        sf = getattr(self, f"_sf_{key}")
        for w in sf.winfo_children():
            w.destroy()

        data = self._loader.get_dataset(key) or []
        total = len(data)

        # apply search filter
        q = self._search_vars.get(key, ctk.StringVar()).get().lower()
        filtered = [item for item in data if q in str(item).lower()] if q else data

        cnt_lbl = getattr(self, f"_cnt_{key}", None)
        if cnt_lbl:
            cnt_lbl.configure(text=f"{total} entries")

        if not filtered:
            self._render_empty(sf, "No items found." if q else "No items in this dataset yet.")
            return

        for item in filtered:
            row = ctk.CTkFrame(sf, fg_color=get_color("ROW_BG"), corner_radius=6)
            row.pack(fill="x", padx=8, pady=3)
            row.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(row, text=str(item), font=get_font_body(),
                         text_color=get_color("TEXT_PRIMARY")).grid(
                row=0, column=0, sticky="w", padx=12, pady=7)
            ctk.CTkButton(
                row, text="✕", width=28, height=24, corner_radius=4,
                font=get_font_body("bold"), fg_color="transparent",
                hover_color=get_color("CRITICAL"), text_color=get_color("TEXT_SECONDARY"),
                command=lambda k=key, i=item: self._cmd_del_list(k, i),
            ).grid(row=0, column=1, padx=6)

    def _populate_dict(self, key: str):
        sf = getattr(self, f"_sf_{key}")
        for w in sf.winfo_children():
            w.destroy()

        data = self._loader.get_dataset(key) or {}
        total = len(data)

        cnt_lbl = getattr(self, f"_cnt_{key}", None)
        if cnt_lbl:
            cnt_lbl.configure(text=f"{total} entries")

        q = self._search_vars.get(key, ctk.StringVar()).get().lower()
        items = list(data.items())
        if q:
            items = [(k, v) for k, v in items if q in k.lower() or q in str(v).lower()]

        if not items:
            self._render_empty(sf, "No matching entries." if q else "No entries yet.")
            return

        for k_str, v_str in items[:200]:
            row = ctk.CTkFrame(sf, fg_color=get_color("ROW_BG"), corner_radius=6)
            row.pack(fill="x", padx=8, pady=3)
            row.grid_columnconfigure((0, 1), weight=1)

            ctk.CTkLabel(row, text=str(k_str), font=get_font_body("bold"),
                         text_color=get_color("TEXT_PRIMARY")).grid(
                row=0, column=0, sticky="w", padx=12, pady=7)
            ctk.CTkLabel(row, text=str(v_str)[:80], font=get_font_body(),
                         text_color=get_color("TEXT_SECONDARY")).grid(
                row=0, column=1, sticky="w", padx=12, pady=7)

            ctk.CTkButton(
                row, text="✕", width=28, height=24, corner_radius=4,
                font=get_font_body("bold"), fg_color="transparent",
                hover_color=get_color("CRITICAL"), text_color=get_color("TEXT_SECONDARY"),
                command=lambda kk=key, ik=k_str: self._cmd_del_dict(kk, ik),
            ).grid(row=0, column=2, padx=6)

    # ─── Validators populate ────────────────────────────────────────────────

    def _populate_validators(self):
        sf = self._validators_sf
        for w in sf.winfo_children():
            w.destroy()

        data: dict = self._loader.get_dataset("custom_rules") or {}
        if not data:
            self._render_empty(sf, "No validators found.")
            return

        # Friendly names for known validators
        FRIENDLY = {
            "spelling_validation":          ("Spelling Validation",        "Checks for misspelled words against the knowledge base."),
            "date_validation":              ("Date Format Validation",      "Flags dates not matching approved formats."),
            "serial_number_validation":     ("Serial Number Validation",    "Validates document serial number presence and format."),
            "page_number_validation":       ("Page Number Validation",      "Checks page numbering continuity."),
            "empty_page_validation":        ("Empty Page Detection",        "Identifies pages with insufficient content."),
            "alignment_validation":         ("Text Alignment Validation",   "Detects inconsistent text alignment."),
            "required_section_validation":  ("Required Section Validator",  "Ensures all mandatory sections are present."),
            "vulnerability_validation":     ("Vulnerability Detection",     "Scans for known security vulnerability patterns."),
            "terminology_validation":       ("Terminology Validation",      "Checks correct use of approved organisational terms."),
        }

        self._validator_switches: dict[str, ctk.CTkSwitch]  = {}
        self._validator_penalties: dict[str, ctk.CTkOptionMenu] = {}

        for key, cfg in data.items():
            enabled  = cfg.get("enabled", True)
            penalty  = cfg.get("penalty", "Warning")
            friendly, desc = FRIENDLY.get(key, (key.replace("_", " ").title(), ""))

            card = ctk.CTkFrame(sf, fg_color=get_color("ROW_BG"), corner_radius=8)
            card.pack(fill="x", padx=8, pady=4)
            card.grid_columnconfigure(1, weight=1)

            # Left: toggle
            sw = ctk.CTkSwitch(
                card, text="", width=44, height=22,
                progress_color=get_color("SUCCESS"),
                fg_color=get_color("BORDER"),
                command=lambda k=key: self._cmd_validator_toggle(k),
            )
            sw.grid(row=0, column=0, rowspan=2, padx=(16, 12), pady=12)
            if enabled:
                sw.select()
            else:
                sw.deselect()
            self._validator_switches[key] = sw

            # Middle: name + desc
            ctk.CTkLabel(card, text=friendly, font=get_font_body("bold"),
                         text_color=get_color("TEXT_PRIMARY")).grid(
                row=0, column=1, sticky="w", padx=0, pady=(12, 2))
            ctk.CTkLabel(card, text=desc, font=get_font_caption(),
                         text_color=get_color("TEXT_SECONDARY")).grid(
                row=1, column=1, sticky="w", pady=(0, 12))

            # Right: severity dropdown
            sev_badge_color = get_color(
                "CRITICAL" if penalty == "Critical" else
                "WARNING"  if penalty == "Warning"  else "TEXT_SECONDARY"
            )
            pen_menu = ctk.CTkOptionMenu(
                card, values=PENALTY_OPTIONS, width=130,
                font=get_font_caption("bold"), fg_color=get_color("APP_BG"),
                button_color=get_color("APP_BG"), button_hover_color=get_color("BORDER"),
                text_color=sev_badge_color, dropdown_fg_color=get_color("CARD_BG"),
                dropdown_text_color=get_color("TEXT_PRIMARY"),
                command=lambda val, k=key: self._cmd_validator_penalty(k, val),
            )
            pen_menu.set(penalty)
            pen_menu.grid(row=0, column=2, rowspan=2, padx=16, pady=12)
            self._validator_penalties[key] = pen_menu

        if self._validators_json_visible:
            self._populate_raw_json("custom_rules")

    def _populate_raw_json(self, key: str):
        textbox = getattr(self, f"_textbox_{key}", None)
        if textbox:
            data = self._loader.get_dataset(key)
            textbox.delete("1.0", "end")
            textbox.insert("1.0", json.dumps(data, indent=4) if data else "{}")

    # ─── Vulnerability KB populate ──────────────────────────────────────────

    def _load_vuln_data(self):
        raw = self._loader.get_dataset("vulnerabilities")
        if isinstance(raw, list):
            self._vuln_data = raw
        else:
            self._vuln_data = []
        
        # Preserve selection if valid, otherwise reset
        if self._selected_vuln_idx is not None and (self._selected_vuln_idx < 0 or self._selected_vuln_idx >= len(self._vuln_data)):
            self._selected_vuln_idx = None
            
        print(f"Rendering vulnerabilities: {len(self._vuln_data)}")
        self._populate_vuln_list()

    def _populate_vuln_list(self):
        for w in self._vuln_list_frame.winfo_children():
            w.destroy()

        q = self._vuln_search_var.get().lower()
        filtered = []
        for idx, v in enumerate(self._vuln_data):
            title = v.get("title", "Untitled")
            sev   = v.get("severity", "Medium")
            kws   = " ".join(v.get("keywords", []))
            if q and q not in title.lower() and q not in sev.lower() and q not in kws.lower():
                continue
            filtered.append((idx, v))

        self._vuln_count_lbl.configure(text=f"{len(self._vuln_data)} vulnerabilities")

        if not filtered:
            self._render_empty(self._vuln_list_frame, "No matching vulnerabilities.")
            return

        for orig_idx, v in filtered:
            title = v.get("title", "Untitled")
            sev   = v.get("severity", "Medium")
            color = get_color(SEVERITY_COLORS.get(sev, "TEXT_SECONDARY"))

            is_sel = (orig_idx == self._selected_vuln_idx)
            bg = get_color("ACCENT") if is_sel else get_color("ROW_BG")

            card = ctk.CTkFrame(self._vuln_list_frame, fg_color=bg, corner_radius=6,
                                cursor="hand2")
            card.pack(fill="x", padx=6, pady=3)
            card.grid_columnconfigure(0, weight=1)
            card.bind("<Button-1>", lambda e, i=orig_idx: self._select_vuln(i))

            ctk.CTkLabel(card, text=title, font=get_font_body("bold"),
                         text_color=get_color("TEXT_PRIMARY"),
                         wraplength=200, anchor="w").grid(
                row=0, column=0, sticky="w", padx=12, pady=(8, 2))

            sev_frame = ctk.CTkFrame(card, fg_color=color, corner_radius=4)
            sev_frame.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))
            ctk.CTkLabel(sev_frame, text=sev, font=get_font_caption("bold"),
                         text_color="#FFFFFF").pack(padx=8, pady=2)

            # Bind children too so clicks register on labels
            for child in card.winfo_children():
                child.bind("<Button-1>", lambda e, i=orig_idx: self._select_vuln(i))
            for child in card.winfo_children():
                for grandchild in child.winfo_children():
                    grandchild.bind("<Button-1>", lambda e, i=orig_idx: self._select_vuln(i))

    def _select_vuln(self, idx: int):
        self._selected_vuln_idx = idx
        self._populate_vuln_list()  # re-render to highlight
        self._load_vuln_form(idx)

    def _load_vuln_form(self, idx: int):
        if idx < 0 or idx >= len(self._vuln_data):
            return
        v = self._vuln_data[idx]

        self._vuln_f_title.delete(0, "end")
        self._vuln_f_title.insert(0, v.get("title", ""))

        self._vuln_f_severity.set(v.get("severity", "Medium"))

        self._vuln_f_keywords.delete(0, "end")
        self._vuln_f_keywords.insert(0, ", ".join(v.get("keywords", [])))

        self._vuln_f_desc.delete("1.0", "end")
        self._vuln_f_desc.insert("1.0", v.get("description", ""))

        self._vuln_f_rem.delete("1.0", "end")
        self._vuln_f_rem.insert("1.0", v.get("remediation", ""))

    def _clear_vuln_form(self):
        self._vuln_f_title.delete(0, "end")
        self._vuln_f_severity.set("Medium")
        self._vuln_f_keywords.delete(0, "end")
        self._vuln_f_desc.delete("1.0", "end")
        self._vuln_f_rem.delete("1.0", "end")

    def _collect_vuln_form(self) -> Optional[Dict]:
        title = self._vuln_f_title.get().strip()
        if not title:
            CustomDialog("Validation Error", "Vulnerability title cannot be empty.", "error").show()
            return None
        kw_raw  = self._vuln_f_keywords.get().strip()
        keywords = [k.strip() for k in kw_raw.split(",") if k.strip()] if kw_raw else []
        return {
            "id":          "",           # filled by caller
            "title":       title,
            "severity":    self._vuln_f_severity.get(),
            "keywords":    keywords,
            "description": self._vuln_f_desc.get("1.0", "end").strip(),
            "remediation": self._vuln_f_rem.get("1.0", "end").strip(),
        }

    def _save_vuln_dataset(self):
        self._loader._save_dataset("vulnerabilities", self._vuln_data)

    # ═══════════════════════════════════════════════════════════════════════
    # RENDER HELPERS
    # ═══════════════════════════════════════════════════════════════════════

    def _render_empty(self, parent, text: str):
        empty = ctk.CTkFrame(parent, fg_color="transparent")
        empty.pack(expand=True, fill="both", pady=32)
        ctk.CTkLabel(empty, text="🗂️", font=("Segoe UI", 36)).pack(pady=(0, 8))
        ctk.CTkLabel(empty, text="No Items Found", font=get_font_h3(),
                     text_color=get_color("TEXT_PRIMARY")).pack(pady=(0, 4))
        ctk.CTkLabel(empty, text=text, font=get_font_body(),
                     text_color=get_color("TEXT_SECONDARY")).pack()

    # ═══════════════════════════════════════════════════════════════════════
    # COMMANDS
    # ═══════════════════════════════════════════════════════════════════════

    # ─── List commands ──────────────────────────────────────────────────────

    def _cmd_add_list(self, key: str, entry: ctk.CTkEntry):
        val = entry.get().strip()
        if not val:
            return
        data = self._loader.get_dataset(key) or []
        if isinstance(data, list) and val not in data:
            data.append(val)
            self._loader._save_dataset(key, data)
            entry.delete(0, "end")
            self._populate_list(key)
            self._refresh_diagnostics()
            log_activity(f"Added item '{val}' to {key}", "Knowledge Base Updated", val)

    def _cmd_del_list(self, key: str, val: str):
        if not CustomDialog("Confirm Delete", f"Remove '{val}' from {key}?", "confirm").show():
            return
        data = self._loader.get_dataset(key) or []
        if isinstance(data, list) and val in data:
            data.remove(val)
            self._loader._save_dataset(key, data)
            self._populate_list(key)
            self._refresh_diagnostics()
            log_activity(f"Removed item '{val}' from {key}", "Knowledge Base Updated", val)

    # ─── Dict commands ──────────────────────────────────────────────────────

    def _cmd_add_dict(self, key: str, e1: ctk.CTkEntry, e2: ctk.CTkEntry):
        k = e1.get().strip()
        v = e2.get().strip()
        if not k:
            return
        data = self._loader.get_dataset(key) or {}
        if isinstance(data, dict):
            data[k] = v
            self._loader._save_dataset(key, data)
            e1.delete(0, "end")
            e2.delete(0, "end")
            self._populate_dict(key)
            self._refresh_diagnostics()
            log_activity(f"Added pair '{k}': '{v}' to {key}", "Knowledge Base Updated", k)

    def _cmd_del_dict(self, key: str, k: str):
        if not CustomDialog("Confirm Delete", f"Remove '{k}' from {key}?", "confirm").show():
            return
        data = self._loader.get_dataset(key) or {}
        if isinstance(data, dict) and k in data:
            del data[k]
            self._loader._save_dataset(key, data)
            self._populate_dict(key)
            self._refresh_diagnostics()
            log_activity(f"Removed '{k}' from {key}", "Knowledge Base Updated", k)

    # ─── Validator commands ─────────────────────────────────────────────────

    def _cmd_validator_toggle(self, key: str):
        data: dict = self._loader.get_dataset("custom_rules") or {}
        if key in data:
            sw = self._validator_switches.get(key)
            enabled = bool(sw and sw.get()) if sw else True
            data[key]["enabled"] = enabled
            self._loader._save_dataset("custom_rules", data)
            log_activity(f"Validator '{key}' toggled to {'Enabled' if enabled else 'Disabled'}", "Knowledge Base Updated", key)
            if self._validators_json_visible:
                self._populate_raw_json("custom_rules")

    def _cmd_validator_penalty(self, key: str, value: str):
        data: dict = self._loader.get_dataset("custom_rules") or {}
        if key in data:
            data[key]["penalty"] = value
            self._loader._save_dataset("custom_rules", data)
            log_activity(f"Validator '{key}' penalty set to '{value}'", "Knowledge Base Updated", key)
            # update text colour of the option menu
            pen_menu = self._validator_penalties.get(key)
            if pen_menu:
                color = get_color(
                    "CRITICAL" if value == "Critical" else
                    "WARNING"  if value == "Warning"  else "TEXT_SECONDARY"
                )
                pen_menu.configure(text_color=color)
            if self._validators_json_visible:
                self._populate_raw_json("custom_rules")

    def _cmd_save_raw_json(self, key: str):
        textbox = getattr(self, f"_textbox_{key}", None)
        if not textbox:
            return
        raw = textbox.get("1.0", "end").strip()
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("Root must be a JSON object {}.")
            self._loader._save_dataset(key, data)
            log_activity(f"Saved raw JSON for {key}", "Knowledge Base Updated", key)
            CustomDialog("Saved", "Validators JSON saved successfully.", "success").show()
            self._populate_validators()
        except Exception as exc:
            CustomDialog("JSON Error", f"Invalid JSON:\n{exc}", "error").show()

    # ─── Vulnerability KB commands ──────────────────────────────────────────

    def _cmd_vuln_save(self):
        form = self._collect_vuln_form()
        if form is None:
            return

        is_new = self._selected_vuln_idx is None or self._selected_vuln_idx < 0 or self._selected_vuln_idx >= len(self._vuln_data)
        if not is_new:
            # Update existing
            existing_id = self._vuln_data[self._selected_vuln_idx].get("id", str(uuid.uuid4()))
            form["id"] = existing_id
            self._vuln_data[self._selected_vuln_idx] = form
        else:
            # New entry
            form["id"] = str(uuid.uuid4())
            self._vuln_data.append(form)
            self._selected_vuln_idx = len(self._vuln_data) - 1

        self._save_vuln_dataset()
        self._refresh_all()
        log_activity(f"{'Created' if is_new else 'Updated'} vulnerability: {form['title']}", "Knowledge Base Updated", form["title"])

    def _cmd_vuln_new(self):
        self._selected_vuln_idx = None
        self._clear_vuln_form()
        self._populate_vuln_list()

    def _cmd_vuln_delete(self):
        if self._selected_vuln_idx is None:
            CustomDialog("No Selection", "Select a vulnerability from the list first.", "error").show()
            return
        if self._selected_vuln_idx >= len(self._vuln_data):
            return
        title = self._vuln_data[self._selected_vuln_idx].get("title", "this entry")
        if not CustomDialog("Confirm Delete",
                            f"Permanently delete '{title}'?\nThis cannot be undone.",
                            "confirm").show():
            return
        del self._vuln_data[self._selected_vuln_idx]
        self._selected_vuln_idx = None
        self._clear_vuln_form()
        self._save_vuln_dataset()
        self._refresh_all()
        log_activity(f"Deleted vulnerability: {title}", "Knowledge Base Updated", title)

    def _cmd_vuln_import(self):
        """Import vulnerabilities from an external JSON file via tkinter file dialog."""
        import tkinter.filedialog as fd
        path = fd.askopenfilename(
            title="Import Vulnerability JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                new_data = json.load(f)
            if not isinstance(new_data, list):
                raise ValueError("JSON root must be a list of vulnerability objects.")
            merged = {v.get("id", v.get("title", "")): v for v in self._vuln_data}
            for entry in new_data:
                eid = entry.get("id") or str(uuid.uuid4())
                entry["id"] = eid
                merged[eid] = entry
            self._vuln_data = list(merged.values())
            self._save_vuln_dataset()
            self._refresh_all()
            log_activity(f"Imported {len(new_data)} vulnerabilities", "Knowledge Base Updated")
            CustomDialog("Import Successful",
                         f"Imported {len(new_data)} entries. Total: {len(self._vuln_data)}.",
                         "success").show()
        except Exception as exc:
            CustomDialog("Import Failed", f"Could not import file:\n{exc}", "error").show()

    def _cmd_vuln_export(self):
        """Export vulnerabilities to an external JSON file via tkinter file dialog."""
        import tkinter.filedialog as fd
        path = fd.asksaveasfilename(
            title="Export Vulnerability KB",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="vulnerabilities_export.json",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._vuln_data, f, indent=4)
            CustomDialog("Export Successful", f"Exported to:\n{path}", "success").show()
        except Exception as exc:
            CustomDialog("Export Failed", f"Could not export:\n{exc}", "error").show()

    # ─── Engine commands ────────────────────────────────────────────────────

    def _cmd_reload_rules(self):
        self._loader._load_all()
        self._refresh_all()
        log_activity("Knowledge Base rules reloaded", "Rule Reloaded")
        CustomDialog("Reloaded", "All rules and datasets have been hot-reloaded from disk.",
                     "success").show()

    def _cmd_backup_all(self):
        bdir = get_backups_dir()
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        target = os.path.join(bdir, f"backup_{ts}")
        os.makedirs(target, exist_ok=True)
        try:
            for f in glob.glob(os.path.join(get_rules_path(""), "*.json")):
                shutil.copy(f, target)
            for f in glob.glob(os.path.join(get_rules_path(""), "*.txt")):
                shutil.copy(f, target)
            CustomDialog("Backup Successful", f"Rules backed up to:\n{target}", "success").show()
        except Exception as exc:
            CustomDialog("Backup Error", f"Failed to backup:\n{exc}", "error").show()

    # ─── Helpers ────────────────────────────────────────────────────────────

    def _notify_dashboard(self, message: str, event_type: str):
        dash = self._main_window._pages.get("dashboard")
        if dash:
            dash._add_activity(message, event_type)
