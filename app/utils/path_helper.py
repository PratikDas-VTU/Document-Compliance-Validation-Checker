"""
path_helper.py — Resolves paths for rules datasets and reports folder,
working both in development mode and when packaged with PyInstaller.
"""
import sys
import os


def get_base_path() -> str:
    """Return the base path of the application (source of bundled read-only assets)."""
    if getattr(sys, "frozen", False):
        # Running inside a PyInstaller bundle — assets are in _MEIPASS
        return sys._MEIPASS  # type: ignore
    # Running from source
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_writable_base() -> str:
    """
    Return the writable base directory. Ensures it is local to the executable in frozen mode.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_rules_path(filename: str = "") -> str:
    """Return the absolute path for a rule file or the rules directory."""
    if not filename:
        return os.path.join(get_writable_base(), "rules")
    
    writable = os.path.join(get_writable_base(), "rules", filename)
    bundled = os.path.join(get_base_path(), "rules", filename)
    if os.path.exists(bundled) and not os.path.exists(writable):
        return bundled
    return writable


def get_data_path(filename: str = "") -> str:
    """Return the absolute path for a persistent data file or the data directory."""
    data_dir = os.path.join(get_writable_base(), "data")
    if not filename:
        return data_dir
    return os.path.join(data_dir, filename)


def get_reports_path(filename: str = "") -> str:
    """Return the absolute path for a report file or the reports directory."""
    from app.ui.theme import TM
    custom_dir = TM.get_setting("custom_reports_dir")
    if custom_dir and os.path.isdir(custom_dir):
        reports_dir = custom_dir
    else:
        reports_dir = os.path.join(get_writable_base(), "reports")
    if not filename:
        return reports_dir
    return os.path.join(reports_dir, filename)


def get_exports_path(filename: str = "") -> str:
    """Return the absolute path for an export file or the exports directory."""
    exports_dir = os.path.join(get_writable_base(), "exports")
    if not filename:
        return exports_dir
    return os.path.join(exports_dir, filename)


def get_logs_path(filename: str = "") -> str:
    """Return the absolute path for a log file or the logs directory."""
    logs_dir = os.path.join(get_writable_base(), "logs")
    if not filename:
        return logs_dir
    return os.path.join(logs_dir, filename)


def get_logo_repository_path(filename: str = "") -> str:
    """Return the absolute path for an organization logo or the logos directory."""
    logo_dir = os.path.join(get_writable_base(), "organization_logos")
    if not filename:
        return logo_dir
    return os.path.join(logo_dir, filename)


def get_assets_path(filename: str = "") -> str:
    """Return the absolute path for an asset file or the assets directory (bundled inside application resources)."""
    # Assets are read-only and stay bundled
    if not filename:
        return os.path.join(get_base_path(), "assets")
    return os.path.join(get_base_path(), "assets", filename)


def get_backups_dir() -> str:
    """Return the absolute path for the rules backups directory."""
    path = os.path.join(get_writable_base(), "rules", "backups")
    os.makedirs(path, exist_ok=True)
    return path


def get_reports_dir() -> str:
    """Backwards-compatible wrapper alias mapping to get_reports_path()."""
    path = get_reports_path()
    os.makedirs(path, exist_ok=True)
    return path


def get_data_dir() -> str:
    """Backwards-compatible wrapper alias mapping to get_data_path()."""
    path = get_data_path()
    os.makedirs(path, exist_ok=True)
    return path


def get_icon_path() -> str:
    """Return the absolute path to assets/app_icon.ico."""
    return get_assets_path("app_icon.ico")


def bootstrap_runtime() -> None:
    """
    Bootstraps all required runtime folders and JSON files on first launch.
    Idempotent, safe to run on every startup, and preserves existing configuration.
    """
    import shutil
    import json
    
    # 1. Create all required directories
    dirs = [
        get_rules_path(""),
        get_data_path(""),
        get_exports_path(""),
        get_reports_path(""),
        get_logs_path(""),
        get_logo_repository_path(""),
        os.path.join(get_writable_base(), "assets") # writable assets folder is created, though empty
    ]
    for path in dirs:
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as e:
            print(f"Bootstrap warning: Failed to create directory '{path}': {e}")

    # 2. Bootstrap JSON files in rules/ with JSON copy priority
    rules_files = {
        "standard_english.json": [],
        "words_dictionary.json": [],
        "cybersecurity_terms.json": [],
        "organization_terms.json": [],
        "whitelist.json": [],
        "security_tools.json": [],
        "network_vendors.json": [],
        "acronyms.json": {},
        "required_sections.json": [],
        "section_aliases.json": {},
        "format_rules.json": {
            "date_formats": ["DD/MM/YYYY", "MM/DD/YYYY", "DD-MMM-YYYY", "YYYY-MM-DD"],
            "empty_page_threshold_chars": 20
        },
        "custom_rules.json": {},
        "cli_commands.json": [],
        "vulnerabilities.json": [],
        "learning_queue.json": [],
        "validators.json": {},
        "dictionary.json": {}
    }

    for fname, fallback in rules_files.items():
        writable_file = os.path.join(get_writable_base(), "rules", fname)
        if not os.path.exists(writable_file):
            bundled_file = os.path.join(get_base_path(), "rules", fname)
            if os.path.exists(bundled_file):
                try:
                    shutil.copy2(bundled_file, writable_file)
                except Exception as e:
                    print(f"Bootstrap warning: Failed to copy bundled default {fname}: {e}")
            else:
                try:
                    with open(writable_file, "w", encoding="utf-8") as f:
                        json.dump(fallback, f, indent=4)
                except Exception as e:
                    print(f"Bootstrap warning: Failed to create fallback {fname}: {e}")

    # 3. Create data/runtime_manifest.json if missing
    manifest_path = get_data_path("runtime_manifest.json")
    if not os.path.exists(manifest_path):
        manifest_data = {
            "version": "1.0.0",
            "initialized": True
        }
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, indent=4)
        except Exception as e:
            print(f"Bootstrap warning: Failed to create manifest: {e}")



def _migrate_legacy_data():
    """Migrate data from legacy dist/rules and dist/reports to persistent location."""
    import shutil
    
    # Migrate legacy telemetry files from default reports/ to data/ (both dev and frozen mode)
    reports_dir = os.path.join(get_writable_base(), "reports")
    data_dir = get_data_dir()
    telemetry_files = [
        "scan_history.json",
        "activity_log.json",
        "kb_state.json",
        "last_scan_diagnostics.json",
        "last_scan_performance.json",
        "settings.json",
        "learning_stats.json",
        "discovery_stats.json"
    ]
    for fname in telemetry_files:
        src = os.path.join(reports_dir, fname)
        dst = os.path.join(data_dir, fname)
        if os.path.exists(src) and not os.path.exists(dst):
            try:
                shutil.move(src, dst)
            except Exception:
                pass

    if not getattr(sys, "frozen", False):
        return
        
    legacy_base = os.path.dirname(sys.executable) # inside dist/
    persistent_base = get_writable_base()
    
    if legacy_base == persistent_base:
        return

    # Migrate Rules
    legacy_rules = os.path.join(legacy_base, "rules")
    persistent_rules = os.path.join(persistent_base, "rules")
    if os.path.exists(legacy_rules):
        os.makedirs(persistent_rules, exist_ok=True)
        for item in os.listdir(legacy_rules):
            s = os.path.join(legacy_rules, item)
            d = os.path.join(persistent_rules, item)
            if not os.path.exists(d):
                try:
                    if os.path.isdir(s): shutil.copytree(s, d)
                    else: shutil.copy2(s, d)
                except Exception: pass

    # Migrate Reports
    legacy_reports = os.path.join(legacy_base, "reports")
    persistent_reports = os.path.join(persistent_base, "reports")
    if os.path.exists(legacy_reports):
        os.makedirs(persistent_reports, exist_ok=True)
        for item in os.listdir(legacy_reports):
            s = os.path.join(legacy_reports, item)
            d = os.path.join(persistent_reports, item)
            if not os.path.exists(d):
                try:
                    if os.path.isdir(s): shutil.copytree(s, d)
                    else: shutil.copy2(s, d)
                except Exception: pass

_migrate_legacy_data()
