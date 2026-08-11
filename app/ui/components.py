"""
components.py — Reusable UI Components.
Includes StatusBadges and blocking CustomDialogs for the Enterprise layer.
"""
import customtkinter as ctk
from app.ui.theme import get_color, get_font_h2, get_font_body, get_font_caption, RADIUS, BORDER_WIDTH

class StatusBadge(ctk.CTkFrame):
    def __init__(self, parent, state: str, **kwargs):
        super().__init__(parent, corner_radius=6, border_width=1, **kwargs)
        self.grid_propagate(False)
        self._lbl = ctk.CTkLabel(self, text="", font=get_font_caption("bold"), text_color="#FFFFFF")
        self._lbl.pack(padx=8, pady=2, expand=True)
        self.set_state(state)

    def set_state(self, state: str):
        state = state.capitalize()
        self._lbl.configure(text=state.upper())
        
        color = get_color("TEXT_SECONDARY") # default
        
        if state in ["Ready", "Exported", "Compliant", "Success"]:
            color = get_color("SUCCESS")
        elif state in ["Scanning", "Processing", "Information", "Active"]:
            color = get_color("ACCENT")
        elif state in ["Warning", "Partial"]:
            color = get_color("WARNING")
        elif state in ["Critical", "Failed", "Non-compliant"]:
            color = get_color("CRITICAL")

        self.configure(fg_color=color, border_color=color)

class CustomDialog(ctk.CTkToplevel):
    """
    A custom, modern modal dialog that returns a string result or boolean.
    Use .show() to block and wait for user response.
    """
    def __init__(self, title: str, message: str, dialog_type: str = "info", **kwargs):
        super().__init__(**kwargs)
        self.title(title)
        self.geometry("460x240")
        self.resizable(False, False)
        
        # Load window icon defensively
        try:
            import os
            from app.utils.path_helper import get_icon_path
            icon_path = get_icon_path()
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass
        
        # Make modal
        self.transient()
        self.grab_set()
        
        self.configure(fg_color=get_color("APP_BG"))
        self._result = None
        self._dialog_type = dialog_type

        # Build UI
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=32, pady=(32, 16))
        
        icon = "ℹ️"
        color = get_color("ACCENT")
        if dialog_type == "success":
            icon = "✓"
            color = get_color("SUCCESS")
        elif dialog_type == "warning" or dialog_type == "confirm":
            icon = "⚠️"
            color = get_color("WARNING")
        elif dialog_type == "error":
            icon = "✕"
            color = get_color("CRITICAL")
            
        ctk.CTkLabel(hdr, text=icon, font=ctk.CTkFont(size=24), text_color=color).pack(side="left", padx=(0, 16))
        ctk.CTkLabel(hdr, text=title, font=get_font_h2(), text_color=get_color("TEXT_PRIMARY")).pack(side="left")

        # Message
        msg_frame = ctk.CTkFrame(self, fg_color="transparent")
        msg_frame.grid(row=1, column=0, sticky="nsew", padx=32)
        ctk.CTkLabel(
            msg_frame, text=message, font=get_font_body(), 
            text_color=get_color("TEXT_SECONDARY"), justify="left", wraplength=380
        ).pack(anchor="nw")

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=32, pady=(16, 32))
        btn_frame.grid_columnconfigure(0, weight=1)

        btn_box = ctk.CTkFrame(btn_frame, fg_color="transparent")
        btn_box.grid(row=0, column=0, sticky="e")

        if dialog_type == "confirm":
            ctk.CTkButton(
                btn_box, text="Cancel", font=get_font_body("bold"), width=100, height=36, corner_radius=8,
                fg_color=get_color("ROW_BG"), hover_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"),
                command=self._cancel
            ).pack(side="left", padx=(0, 12))
            
            ctk.CTkButton(
                btn_box, text="Confirm", font=get_font_body("bold"), width=100, height=36, corner_radius=8,
                fg_color=get_color("CRITICAL"), hover_color=get_color("BORDER"),
                command=self._confirm
            ).pack(side="left")
        else:
            ctk.CTkButton(
                btn_box, text="Close", font=get_font_body("bold"), width=100, height=36, corner_radius=8,
                fg_color=get_color("ACCENT") if dialog_type != "error" else get_color("ROW_BG"), 
                hover_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"),
                command=self._confirm
            ).pack(side="left")

    def _confirm(self):
        self._result = True
        self.destroy()

    def _cancel(self):
        self._result = False
        self.destroy()

    def show(self):
        self.wait_window()
        return self._result

class ExportSuccessDialog(ctk.CTkToplevel):
    """
    A dedicated dialog for handling export success, showing the path, 
    and offering options to Open Report, Open Folder, and Close.
    """
    def __init__(self, file_path: str, initial_auto_open: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.title("Export Complete")
        self.geometry("640x380")
        self.minsize(640, 380)
        self.resizable(False, False)
        
        # Load window icon defensively
        try:
            import os
            from app.utils.path_helper import get_icon_path
            icon_path = get_icon_path()
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass
        
        self.transient()
        self.grab_set()
        
        self.configure(fg_color=get_color("APP_BG"))
        self._result = "close"
        self.auto_open_var = ctk.BooleanVar(value=initial_auto_open)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=32, pady=(32, 16))
        
        ctk.CTkLabel(hdr, text="✓", font=ctk.CTkFont(size=24), text_color=get_color("SUCCESS")).pack(side="left", padx=(0, 16))
        ctk.CTkLabel(hdr, text="Export Complete", font=get_font_h2(), text_color=get_color("TEXT_PRIMARY")).pack(side="left")
        
        # Message
        msg_frame = ctk.CTkFrame(self, fg_color="transparent")
        msg_frame.grid(row=1, column=0, sticky="nsew", padx=32)
        
        ctk.CTkLabel(msg_frame, text="Report successfully exported.", font=get_font_body(), text_color=get_color("TEXT_PRIMARY")).pack(anchor="nw", pady=(0, 8))
        
        # Path
        path_box = ctk.CTkFrame(msg_frame, fg_color=get_color("ROW_BG"), corner_radius=6, border_width=1, border_color=get_color("BORDER"))
        path_box.pack(fill="x", pady=8, ipady=8, ipadx=12)
        ctk.CTkLabel(path_box, text="Location:", font=get_font_caption("bold"), text_color=get_color("TEXT_MUTED")).pack(anchor="w")
        
        self.lbl_path = ctk.CTkLabel(path_box, text=file_path, font=get_font_caption(), text_color=get_color("TEXT_SECONDARY"), justify="left", wraplength=520)
        self.lbl_path.pack(anchor="w", pady=(2,0))
        
        # Auto-open checkbox
        cb = ctk.CTkCheckBox(
            msg_frame, text="Automatically open report after export", 
            variable=self.auto_open_var, font=get_font_body(), 
            fg_color=get_color("ACCENT"), hover_color=get_color("BORDER")
        )
        cb.pack(anchor="nw", pady=(16, 0))
        
        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=32, pady=(16, 32))
        btn_frame.grid_columnconfigure(0, weight=1)
        
        btn_box = ctk.CTkFrame(btn_frame, fg_color="transparent")
        btn_box.grid(row=0, column=0, sticky="e")
        
        ctk.CTkButton(
            btn_box, text="Open Report", font=get_font_body("bold"), width=110, height=36, corner_radius=8,
            fg_color=get_color("ACCENT"), hover_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"),
            command=lambda: self._set_result("open_report")
        ).pack(side="left", padx=(0, 12))
        
        ctk.CTkButton(
            btn_box, text="Open Folder", font=get_font_body("bold"), width=110, height=36, corner_radius=8,
            fg_color=get_color("ROW_BG"), hover_color=get_color("BORDER"), text_color=get_color("TEXT_PRIMARY"),
            command=lambda: self._set_result("open_folder")
        ).pack(side="left", padx=(0, 12))
        
        ctk.CTkButton(
            btn_box, text="Close", font=get_font_body("bold"), width=80, height=36, corner_radius=8,
            fg_color=get_color("BORDER"), hover_color=get_color("ROW_BG"), text_color=get_color("TEXT_PRIMARY"),
            command=lambda: self._set_result("close")
        ).pack(side="left")

    def set_warning(self, msg: str):
        self.lbl_path.configure(text_color=get_color("WARNING"))
        self.lbl_path.master.configure(border_color=get_color("WARNING"))
        for w in self.grid_slaves(row=1, column=0):
            for child in w.pack_slaves():
                if isinstance(child, ctk.CTkLabel) and child.cget("text").startswith("Report successfully"):
                    child.configure(text=msg, text_color=get_color("WARNING"))
                    break

    def _set_result(self, res):
        self._result = res
        self.destroy()

    def show(self):
        self.wait_window()
        return self._result, self.auto_open_var.get()
