# -*- mode: python ; coding: utf-8 -*-
"""
ComplianceChecker.spec — PyInstaller spec file.
Bundles the app, rules datasets, and all required packages into a single .exe
"""

import os

# ── Package data paths ─────────────────────────────────────────────────────
import sysconfig
SITE_PACKAGES = sysconfig.get_paths()["purelib"]

CTK_PATH       = os.path.join(SITE_PACKAGES, "customtkinter")
FITZ_PATH      = os.path.join(SITE_PACKAGES, "fitz")
DOCX_PATH      = os.path.join(SITE_PACKAGES, "docx")
REPORTLAB_PATH = os.path.join(SITE_PACKAGES, "reportlab")
SPELLCHECKER_PATH = os.path.join(SITE_PACKAGES, "spellchecker")

a = Analysis(
    ["run.py"],
    pathex=["."],
    binaries=[],
    datas=[
        # Rules datasets
        ("rules",        "rules"),
        # CustomTkinter themes/assets (critical — must be bundled)
        (CTK_PATH,       "customtkinter"),
        # python-docx default templates
        (DOCX_PATH,      "docx"),
        # ReportLab fonts and config
        (REPORTLAB_PATH, "reportlab"),
        # Spellchecker dictionaries
        (os.path.join(SPELLCHECKER_PATH, "resources"), "spellchecker/resources"),
        # Application icon assets
        ("assets",       "assets"),
    ],
    hiddenimports=[
        # Spellchecker
        "spellchecker",
        # CustomTkinter
        "customtkinter",
        "customtkinter.windows",
        "customtkinter.windows.widgets",
        "customtkinter.windows.widgets.theme",
        "customtkinter.windows.widgets.utility",
        "tkinter",
        "tkinter.ttk",
        "tkinter.filedialog",
        "tkinter.messagebox",
        # PyMuPDF
        "fitz",
        "fitz.fitz",
        # python-docx
        "docx",
        "docx.oxml",
        "docx.oxml.ns",
        "docx.shared",
        "docx.enum",
        "docx.enum.text",
        # ReportLab
        "reportlab",
        "reportlab.lib",
        "reportlab.lib.pagesizes",
        "reportlab.lib.units",
        "reportlab.lib.colors",
        "reportlab.lib.styles",
        "reportlab.lib.enums",
        "reportlab.platypus",
        "reportlab.platypus.flowables",
        "reportlab.pdfgen",
        "reportlab.pdfgen.canvas",
        "reportlab.pdfbase",
        "reportlab.pdfbase.pdfmetrics",
        "reportlab.pdfbase.ttfonts",
        "reportlab.graphics",
        # App modules
        "app",
        "app.main",
        "app.ui",
        "app.ui.main_window",
        "app.ui.dashboard",
        "app.ui.scan_page",
        "app.ui.rules_page",
        "app.ui.reports_page",
        "app.ui.developer_diagnostics",
        "app.parsers",
        "app.parsers.pdf_parser",
        "app.parsers.docx_parser",
        "app.validators",
        "app.validators.base",
        "app.validators.sections",
        "app.validators.date",
        "app.validators.vulnerability",
        "app.validators.terminology",
        "app.validators.spelling",
        "app.validators.empty_page",
        "app.validators.serial_number",
        "app.validators.page_number",
        "app.validators.branding",
        "app.services",
        "app.services.rules_loader",
        "app.services.scanner",
        "app.services.branding_engine",
        "app.services.report_exporter",
        "app.utils",
        "app.utils.path_helper",
        "app.utils.activity_helper",
        "cv2",
        "numpy",
        # Stdlib
        "concurrent.futures",
        "threading",
        "json",
        "re",
        "os",
        "sys",
        "calendar",
        "datetime",
        "subprocess",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "pandas",
        "scipy",
        "IPython",
        "notebook",
        "pytest",
        "sphinx",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ComplianceChecker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # No black console window — pure GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/app_icon.ico",
    # Onefile = single .exe, no folder needed
    onefile=True,
)
