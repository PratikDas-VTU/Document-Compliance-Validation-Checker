"""
reports_page.py — Reports page.
Phase 5C: Status Badges, Empty States, Custom Dialogs.
"""
from __future__ import annotations
import os
import datetime
import subprocess
import sys
import customtkinter as ctk

from app.utils.path_helper import get_reports_dir
from app.ui.theme import get_color, get_font_h1, get_font_h2, get_font_h3, get_font_body, get_font_caption, RADIUS, BORDER_WIDTH
from app.ui.components import StatusBadge, CustomDialog

EXT_COLORS = {
    ".pdf":  "CRITICAL",
    ".docx": "ACCENT",
    ".txt":  "SUCCESS",
}

def _open_file(path: str) -> None:
    try:
        if sys.platform == "win32": os.startfile(path)
        elif sys.platform == "darwin": subprocess.Popen(["open", path])
        else: subprocess.Popen(["xdg-open", path])
    except Exception:
        pass

def _open_folder(path: str) -> None:
    folder = os.path.dirname(path)
    try:
        if sys.platform == "win32": subprocess.Popen(["explorer", folder])
        elif sys.platform == "darwin": subprocess.Popen(["open", folder])
        else: subprocess.Popen(["xdg-open", folder])
    except Exception:
        pass

class ReportsPage(ctk.CTkFrame):
    def __init__(self, parent, main_window, **kwargs):
        print("Reports Page Created")
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._main_window = main_window
        self._last_history_mtime = 0.0

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.grid(row=0, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        self._build()

    def _build(self) -> None:
        S = self._scroll

        # Header
        hdr = ctk.CTkFrame(S, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=32, pady=(28, 24), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(hdr, text="Generated Reports", font=get_font_h1(), text_color=get_color("TEXT_PRIMARY")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(hdr, text="View, manage, and delete exported PDF compliance reports.", font=get_font_body(), text_color=get_color("TEXT_SECONDARY")).grid(row=1, column=0, sticky="w", pady=(4, 0))

        btn_folder = ctk.CTkButton(
            hdr, text="📁 Open Folder", font=get_font_body("bold"), height=36, corner_radius=8,
            fg_color=get_color("ROW_BG"), hover_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"),
            command=lambda: _open_folder(os.path.join(get_reports_dir(), "dummy.txt"))
        )
        btn_folder.grid(row=0, column=1, rowspan=2, sticky="e")

        self._list_frame = ctk.CTkFrame(S, fg_color=get_color("CARD_BG"), corner_radius=RADIUS, border_width=BORDER_WIDTH, border_color=get_color("BORDER"))
        self._list_frame.grid(row=1, column=0, padx=32, pady=(0, 32), sticky="ew")
        self._list_frame.grid_columnconfigure(0, weight=1)

    def on_show(self) -> None:
        import os
        from app.utils.path_helper import get_data_dir
        hist_path = os.path.join(get_data_dir(), "scan_history.json")
        hist_mtime = os.path.getmtime(hist_path) if os.path.exists(hist_path) else 0.0
        if hist_mtime != self._last_history_mtime:
            self._refresh_list()

    def _delete_report(self, fpath: str):
        if CustomDialog("Delete Report?", "Are you sure you want to delete this report?\nThis action cannot be undone.", "confirm").show():
            try:
                os.remove(fpath)
                dash = self._main_window._pages.get("dashboard")
                if dash: dash._add_activity(f"Deleted: {os.path.basename(fpath)}", "Report Deleted")
                self._refresh_list()
            except Exception as e:
                CustomDialog("Delete Failed", str(e), "error").show()

    def _refresh_list(self) -> None:
        import os
        from app.utils.path_helper import get_data_dir
        hist_path = os.path.join(get_data_dir(), "scan_history.json")
        self._last_history_mtime = os.path.getmtime(hist_path) if os.path.exists(hist_path) else 0.0

        for widget in self._list_frame.winfo_children():
            widget.destroy()

        import json
        from app.utils.path_helper import get_data_dir
        
        hist_path = os.path.join(get_data_dir(), "scan_history.json")
        scan_log = []
        if os.path.exists(hist_path):
            try:
                with open(hist_path, "r", encoding="utf-8") as f:
                    scan_log = json.load(f)
            except Exception:
                pass

        files = []
        seen_paths = set()
        
        for s in scan_log:
            full = s.get("exported_path")
            if full:
                from app.utils.path_helper import get_writable_base
                if not os.path.isabs(full):
                    resolved_full = os.path.abspath(os.path.join(get_writable_base(), full))
                else:
                    resolved_full = full
                    if not os.path.exists(resolved_full):
                        parts = resolved_full.split(os.sep)
                        if "reports" in parts:
                            idx = parts.index("reports")
                            sub_path = os.path.join(*parts[idx:])
                            alt_path = os.path.abspath(os.path.join(get_writable_base(), sub_path))
                            if os.path.exists(alt_path):
                                resolved_full = alt_path
                
                if resolved_full not in seen_paths and os.path.isfile(resolved_full):
                    seen_paths.add(resolved_full)
                    fname = os.path.basename(resolved_full)
                    st = os.stat(resolved_full)
                    files.append((fname, resolved_full, st.st_size, st.st_mtime))

        if not files:
            empty = ctk.CTkFrame(self._list_frame, fg_color="transparent")
            empty.grid(row=0, column=0, pady=60)
            
            # Icon
            ico = ctk.CTkLabel(empty, text="📄", font=("Segoe UI", 48))
            ico.pack(pady=(0, 16))

            ctk.CTkLabel(empty, text="No Reports Generated Yet", font=get_font_h3(), text_color=get_color("TEXT_PRIMARY")).pack(pady=(12, 4))
            ctk.CTkLabel(empty, text="Upload a document in Scan Center to generate your first compliance report.", font=get_font_body(), text_color=get_color("TEXT_SECONDARY"), wraplength=250).pack()
            return

        files.sort(key=lambda x: x[3], reverse=True)

        for idx, (fname, fpath, size, mtime) in enumerate(files):
            ext = os.path.splitext(fname)[1].lower()
            color_key = EXT_COLORS.get(ext, "TEXT_SECONDARY")

            row = ctk.CTkFrame(self._list_frame, fg_color=get_color("ROW_BG"), corner_radius=8)
            row.grid(row=idx, column=0, padx=24, pady=(24 if idx == 0 else 8, 24 if idx == len(files)-1 else 8), sticky="ew")
            row.grid_columnconfigure(1, weight=1)

            ico = ctk.CTkFrame(row, fg_color=get_color(color_key), corner_radius=6, width=40, height=40)
            ico.grid(row=0, column=0, padx=16, pady=16)
            ico.grid_propagate(False)
            ctk.CTkLabel(ico, text=ext.upper().replace(".", ""), font=get_font_caption("bold"), text_color="#FFFFFF").place(relx=0.5, rely=0.5, anchor="center")

            det = ctk.CTkFrame(row, fg_color="transparent")
            det.grid(row=0, column=1, sticky="w", pady=16)
            ctk.CTkLabel(det, text=fname, font=get_font_h3(), text_color=get_color("TEXT_PRIMARY")).pack(anchor="w")
            
            dt = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            sz = f"{size / 1024:.1f} KB"
            ctk.CTkLabel(det, text=f"{dt}  •  {sz}", font=get_font_caption(), text_color=get_color("TEXT_SECONDARY")).pack(anchor="w", pady=(4, 0))

            StatusBadge(row, state="Ready").grid(row=0, column=2, padx=16)

            ctk.CTkButton(
                row, text="Open", font=get_font_body("bold"), width=80, height=32, corner_radius=6,
                fg_color=get_color("APP_BG"), hover_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"),
                command=lambda p=fpath: _open_file(p)
            ).grid(row=0, column=3, padx=(0, 8))

            ctk.CTkButton(
                row, text="✕", font=get_font_body("bold"), width=32, height=32, corner_radius=6,
                fg_color=get_color("APP_BG"), hover_color=get_color("CRITICAL"), text_color=get_color("TEXT_PRIMARY"),
                command=lambda p=fpath: self._delete_report(p)
            ).grid(row=0, column=4, padx=(0, 16))
