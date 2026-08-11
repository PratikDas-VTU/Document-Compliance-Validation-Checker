"""
rules_loader.py — Loads and caches all JSON rule datasets from the rules/ folder.
Gracefully handles missing optional files.
Supports hot-reload via reload() for live rule updates.
"""
import json
import os
from typing import Any, Dict, List, Set
from app.utils.path_helper import get_rules_path, get_writable_base


def _load_json(filename: str, fallback: Any) -> Any:
    """Load a JSON file; return fallback if the file is missing or malformed."""
    path = get_rules_path(filename)
    if not os.path.exists(path):
        return fallback
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return fallback


class RulesLoader:
    """Loads all datasets once and provides them as properties. Supports reload()."""
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(RulesLoader, cls).__new__(cls, *args, **kwargs)
            cls._instance.rules_reload_count = 0
            cls._instance.kb_reload_count = 0
            cls._instance.last_reload_time = "Never"
            cls._instance.duplicate_ids_count = 0
            cls._instance.duplicate_titles_count = 0
            cls._instance.missing_keywords_count = 0
            cls._instance.missing_descriptions_count = 0
            cls._instance.missing_remediations_count = 0
            cls._instance.diagnostics_warnings = []
            cls._instance.kb_categories = {}
            cls._instance.diagnostics_meta = {}
            cls._instance._spell_word_count = 0
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._load_all()
        self._initialized = True

    def _run_integrity_check(self) -> None:
        """Run validation checks on vulnerabilities and compute statistics."""
        import os
        import json
        import datetime
        from app.utils.path_helper import get_data_dir, get_rules_path

        self.diagnostics_warnings = []
        self.kb_categories = {}
        
        self.duplicate_ids_count = 0
        self.duplicate_titles_count = 0
        self.missing_keywords_count = 0
        self.missing_descriptions_count = 0
        self.missing_remediations_count = 0
        
        seen_ids = set()
        seen_titles = set()
        for v in self._vulnerabilities:
            vid = v.get("id", "")
            title = v.get("title", "")
            cat = v.get("category", "Uncategorized")
            
            self.kb_categories[cat] = self.kb_categories.get(cat, 0) + 1
            
            if not vid:
                self.diagnostics_warnings.append(f"Missing ID for vulnerability: {title}")
            elif vid in seen_ids:
                self.diagnostics_warnings.append(f"Duplicate ID detected: {vid}")
                self.duplicate_ids_count += 1
            if vid:
                seen_ids.add(vid)
            
            if not title:
                self.diagnostics_warnings.append(f"Missing title for ID: {vid}")
            elif title in seen_titles:
                self.diagnostics_warnings.append(f"Duplicate title detected: {title}")
                self.duplicate_titles_count += 1
            if title:
                seen_titles.add(title)
            
            if not v.get("description"):
                self.diagnostics_warnings.append(f"Empty description for: {vid}")
                self.missing_descriptions_count += 1
            if not v.get("remediation"):
                self.diagnostics_warnings.append(f"Empty remediation for: {vid}")
                self.missing_remediations_count += 1
            if not v.get("keywords"):
                self.diagnostics_warnings.append(f"Missing keywords for: {vid}")
                self.missing_keywords_count += 1
            if v.get("severity", "").lower() not in ["critical", "high", "medium", "low", "info", "informational"]:
                self.diagnostics_warnings.append(f"Invalid severity '{v.get('severity')}' for: {vid}")

        # Consistency check for accidental KB resets
        kb_state_path = os.path.join(get_data_dir(), "kb_state.json")
        current_count = len(self._vulnerabilities)
        last_count = 0
        if os.path.exists(kb_state_path):
            try:
                with open(kb_state_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    last_count = state.get("last_count", 0)
                    if current_count < last_count and current_count < (last_count * 0.5):
                        self.diagnostics_warnings.append(f"CRITICAL: KB count dropped from {last_count} to {current_count}. Possible accidental reset.")
            except Exception:
                pass
            
        try:
            with open(kb_state_path, "w", encoding="utf-8") as f:
                json.dump({"last_count": max(current_count, last_count)}, f)
        except Exception:
            pass

        vuln_path = get_rules_path("vulnerabilities.json")
        last_mod = ""
        if os.path.exists(vuln_path):
            last_mod = datetime.datetime.fromtimestamp(os.path.getmtime(vuln_path)).strftime('%Y-%m-%d %H:%M:%S')
            
        self.diagnostics_meta = {
            "loaded_count": current_count,
            "source_path": vuln_path,
            "last_modified": last_mod,
            "categories": len(self.kb_categories)
        }
        
        print(f"Loaded vulnerabilities: {len(self._vulnerabilities)}")
        print(f"Source File: {vuln_path}")
        print(f"Last Modified: {last_mod}")

    def _load_all(self) -> None:
        """Load (or reload) all datasets from disk."""
        import datetime
        self.rules_reload_count += 1
        self.kb_reload_count += 1
        self.last_reload_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ── Core word lists ───────────────────────────────────────────────────
        self._standard_english: Set[str] = set(
            w.lower() for w in _load_json("standard_english.json", [])
        )
        _extra = _load_json("words_dictionary.json", [])
        if isinstance(_extra, list):
            self._standard_english.update(w.lower() for w in _extra)

        self._cybersecurity_terms: Set[str] = set(
            w.lower() for w in _load_json("cybersecurity_terms.json", [])
        )
        self._organization_terms: Set[str] = set(
            w.lower() for w in _load_json("organization_terms.json", [])
        )
        self._whitelist: Set[str] = set(
            w.lower() for w in _load_json("whitelist.json", [])
        )
        self._security_tools: Set[str] = set(
            w.lower() for w in _load_json("security_tools.json", [])
        )
        self._network_vendors: Set[str] = set(
            w.lower() for w in _load_json("network_vendors.json", [])
        )

        # ── Acronyms ──────────────────────────────────────────────────────────
        _acronyms_raw = _load_json("acronyms.json", {})
        if isinstance(_acronyms_raw, dict):
            self._acronyms: Dict[str, str] = {
                k.upper(): v for k, v in _acronyms_raw.items()
            }
        else:
            self._acronyms = {}

        # ── Combined spelling whitelist ────────────────────────────────────────
        self._spelling_whitelist: Set[str] = (
            self._standard_english
            | self._cybersecurity_terms
            | self._organization_terms
            | self._whitelist
            | self._security_tools
            | self._network_vendors
            | {k.lower() for k in self._acronyms}
        )

        # ── Structural rules ──────────────────────────────────────────────────
        self._required_sections: List[str] = _load_json("required_sections.json", [])

        # Section aliases: {"Executive Summary": ["Overview", "Introduction", ...]}
        _aliases_raw = _load_json("section_aliases.json", {})
        self._section_aliases: Dict[str, List[str]] = (
            _aliases_raw if isinstance(_aliases_raw, dict) else {}
        )

        self._format_rules: Dict[str, Any] = _load_json("format_rules.json", {
            "date_formats": ["DD/MM/YYYY", "MM/DD/YYYY", "DD-MMM-YYYY", "YYYY-MM-DD"],
            "empty_page_threshold_chars": 20,
        })
        self._custom_rules: Dict[str, Any] = _load_json("custom_rules.json", {})
        self._cli_commands: List[str] = _load_json("cli_commands.json", [])

        # ── Vulnerabilities ───────────────────────────────────────────────────
        _vulns = _load_json("vulnerabilities.json", [])
        self._vulnerabilities: List[Dict[str, Any]] = _vulns if isinstance(_vulns, list) else []

        # ── Learning Queue ────────────────────────────────────────────────────
        _lq = _load_json("learning_queue.json", [])
        self._learning_queue: List[Dict[str, Any]] = _lq if isinstance(_lq, list) else []

        self._run_integrity_check()

        # ── Diagnostics ───────────────────────────────────────────────────────
        # Try pyspellchecker word count
        try:
            from spellchecker import SpellChecker
            sc = SpellChecker()
            self._spell_word_count = sum(1 for _ in sc.word_frequency.keys())
        except Exception:
            self._spell_word_count = 0

    def reload(self) -> None:
        """Hot-reload all datasets from disk. Thread-safe for read access after call."""
        self._load_all()

    # ── Public properties ─────────────────────────────────────────────────────

    @property
    def standard_english(self) -> Set[str]:
        return self._standard_english

    @property
    def cybersecurity_terms(self) -> Set[str]:
        return self._cybersecurity_terms

    @property
    def organization_terms(self) -> Set[str]:
        return self._organization_terms

    @property
    def whitelist(self) -> Set[str]:
        return self._whitelist

    @property
    def security_tools(self) -> Set[str]:
        return self._security_tools

    @property
    def network_vendors(self) -> Set[str]:
        return self._network_vendors

    @property
    def acronyms(self) -> Dict[str, str]:
        return self._acronyms

    @property
    def spelling_whitelist(self) -> Set[str]:
        return self._spelling_whitelist

    @property
    def required_sections(self) -> List[str]:
        return self._required_sections

    @property
    def section_aliases(self) -> Dict[str, List[str]]:
        return self._section_aliases

    @property
    def format_rules(self) -> Dict[str, Any]:
        return self._format_rules

    @property
    def custom_rules(self) -> Dict[str, Any]:
        return self._custom_rules

    @property
    def cli_commands(self) -> List[str]:
        return self._cli_commands

    @property
    def vulnerabilities(self) -> List[Dict[str, Any]]:
        return self._vulnerabilities

    @property
    def learning_queue(self) -> List[Dict[str, Any]]:
        return self._learning_queue

    # ── Helpers ───────────────────────────────────────────────────────────────

    def save_learning_queue(self, queue: List[Dict[str, Any]]) -> None:
        import os, json
        from app.utils.path_helper import get_rules_path
        path = get_rules_path("learning_queue.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(queue, f, indent=4)
            self._learning_queue = queue
        except Exception as e:
            print(f"Error saving learning queue: {e}")

    def save_acronyms(self, acronyms: Dict[str, str]) -> None:
        import os, json
        from app.utils.path_helper import get_rules_path
        path = get_rules_path("acronyms.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(acronyms, f, indent=4)
            self._acronyms = {k.upper(): v for k, v in acronyms.items()}
        except Exception as e:
            print(f"Error saving acronyms: {e}")

    def save_organization_terms(self, terms: List[str]) -> None:
        import os, json
        from app.utils.path_helper import get_rules_path
        path = get_rules_path("organization_terms.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(terms, f, indent=4)
            self._organization_terms = set(t.lower() for t in terms)
        except Exception as e:
            print(f"Error saving organization terms: {e}")

    def save_whitelist(self, terms: List[str]) -> None:
        """Persist whitelist modifications."""
        self._save_dataset("whitelist", terms)

    def is_validator_enabled(self, key: str) -> bool:
        rule = self._custom_rules.get(key, {})
        return rule.get("enabled", True)

    def get_penalty(self, key: str) -> str:
        rule = self._custom_rules.get(key, {})
        return rule.get("penalty", "Warning")

    def stats(self) -> Dict[str, Any]:
        """Return a comprehensive stats dictionary for the Rules page diagnostics."""
        return {
            "standard_english":   len(self._standard_english),
            "spell_checker":      self._spell_word_count,
            "cybersecurity_terms": len(self._cybersecurity_terms),
            "organization_terms": len(self._organization_terms),
            "whitelist":          len(self._whitelist),
            "security_tools":     len(self._security_tools),
            "network_vendors":    len(self._network_vendors),
            "acronyms":           len(self._acronyms),
            "required_sections":  self._required_sections,
            "section_aliases":    self._section_aliases,
            "custom_rules":       self._custom_rules,
            "vulnerabilities":    len(self._vulnerabilities),
        }

    def get_dataset(self, key: str) -> Any:
        attr_name = f"_{key}"
        if hasattr(self, attr_name):
            val = getattr(self, attr_name)
            if isinstance(val, set):
                return sorted(list(val))
            return val
        return None

    def load_all(self) -> None:
        """Public alias for _load_all(). Used by UI reload commands."""
        self._load_all()

    def _save_dataset(self, key: str, data: Any) -> None:
        """Persist a dataset to the writable rules directory and update in-memory cache."""
        # Always write to the writable location (not the bundled read-only copy)
        writable_dir = os.path.join(get_writable_base(), "rules")
        os.makedirs(writable_dir, exist_ok=True)
        path = os.path.join(writable_dir, f"{key}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(list(data) if isinstance(data, set) else data, f, indent=4)
        except Exception:
            pass

        # Update in-memory cache without a full reload (performance)
        attr_name = f"_{key}"
        if hasattr(self, attr_name):
            current = getattr(self, attr_name)
            if isinstance(current, set):
                # Rebuild the set from the new data
                if isinstance(data, (list, set)):
                    setattr(self, attr_name, {w.lower() for w in data})
                # Rebuild combined spelling whitelist
                self._spelling_whitelist = (
                    self._standard_english
                    | self._cybersecurity_terms
                    | self._organization_terms
                    | self._whitelist
                    | self._security_tools
                    | self._network_vendors
                    | {k.lower() for k in self._acronyms}
                )
            else:
                setattr(self, attr_name, data)
                if key == "vulnerabilities":
                    self.kb_reload_count += 1
                    import datetime
                    self.last_reload_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self._run_integrity_check()

    def get_source_file_metadata(self, filename: str) -> dict:
        """Returns the file size, last modified timestamp, and status of a JSON rule file."""
        import os, datetime
        from app.utils.path_helper import get_rules_path
        
        path = get_rules_path(filename)
        exists = os.path.exists(path)
        
        if not exists:
            return {
                "status": "Missing",
                "size_bytes": 0,
                "last_modified": "N/A"
            }
            
        try:
            size = os.path.getsize(path)
            mtime = os.path.getmtime(path)
            last_mod = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            return {
                "status": "Loaded",
                "size_bytes": size,
                "last_modified": last_mod
            }
        except Exception:
            return {
                "status": "Error",
                "size_bytes": 0,
                "last_modified": "N/A"
            }

    def get_logo_repository_metadata(self) -> dict:
        """Returns the registered logos count, repository status, total size, and last modified date."""
        import os, datetime
        from app.utils.path_helper import get_logo_repository_path
        
        logo_dir = get_logo_repository_path()
        if not os.path.exists(logo_dir):
            try:
                os.makedirs(logo_dir, exist_ok=True)
            except Exception:
                return {
                    "status": "Missing",
                    "count": 0,
                    "size_bytes": 0,
                    "last_modified": "N/A"
                }
                
        try:
            files = [f for f in os.listdir(logo_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            total_size = 0
            latest_mtime = 0.0
            
            for f in files:
                fpath = os.path.join(logo_dir, f)
                total_size += os.path.getsize(fpath)
                mtime = os.path.getmtime(fpath)
                if mtime > latest_mtime:
                    latest_mtime = mtime
                    
            last_mod = datetime.datetime.fromtimestamp(latest_mtime).strftime("%Y-%m-%d %H:%M") if latest_mtime > 0 else "N/A"
            return {
                "status": "Loaded",
                "count": len(files),
                "size_bytes": total_size,
                "last_modified": last_mod
            }
        except Exception:
            return {
                "status": "Error",
                "count": 0,
                "size_bytes": 0,
                "last_modified": "N/A"
            }
