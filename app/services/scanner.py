"""
scanner.py — Background scanning orchestrator.
Runs document parsing and all validators in a background thread.
Communicates progress and results back to the UI via callback functions,
which are always invoked through root.after() from the UI layer.
Supports cancellation via threading.Event.
"""
from __future__ import annotations
import threading
import traceback
from typing import Callable, Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, Future

from app.parsers.pdf_parser import parse_pdf
from app.parsers.docx_parser import parse_docx
from app.validators.base import Finding, ScanCancelledException
from app.validators.sections import SectionValidator
from app.validators.date import DateValidator
from app.validators.vulnerability import VulnerabilityValidator
from app.validators.terminology import TerminologyValidator
from app.validators.spelling import SpellingValidator
from app.validators.empty_page import EmptyPageValidator
from app.validators.serial_number import SerialNumberValidator
from app.validators.page_number import PageNumberValidator
from app.validators.branding import BrandingValidator
from app.services.rules_loader import RulesLoader


# Scan stages displayed in the progress bar
STAGES = [
    "Parsing Document",
    "Loading Rules",
    "Checking Required Sections",
    "Checking Dates",
    "Checking Vulnerabilities",
    "Checking Terminology",
    "Checking Spelling",
    "Checking Empty Pages",
    "Checking Serial Numbers",
    "Checking Page Numbers",
    "Checking Branding Consistency",
    "Generating Report",
    "Completed",
]


class ScanResult:
    """Holds the complete output of a scan."""
    def __init__(self) -> None:
        self.findings: List[Finding] = []
        self.score: float = 100.0
        self.grade: str = "Compliant"
        self.page_count: int = 0
        self.file_type: str = ""
        self.filename: str = ""
        self.error: Optional[str] = None
        self.cancelled: bool = False
        self.branding_summary: dict = {}
        self.vuln_summary: dict = {}
        self.discovery_candidates: list = []
        self.discovery_summary: dict = {}

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "Critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "Warning")

    @property
    def info_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "Information")

    @property
    def passed_checks(self) -> int:
        return max(0, 8 - len({f.validator for f in self.findings}))


def _calculate_score(findings: List[Finding]) -> tuple:
    """Return (score_float, grade_str)."""
    score = 100.0
    for f in findings:
        if f.severity == "Critical":
            score -= 10.0
        elif f.severity == "Warning":
            score -= 3.0
    score = max(0.0, min(100.0, score))
    if score >= 90:
        grade = "Compliant"
    elif score >= 75:
        grade = "Partially Compliant"
    else:
        grade = "Non-Compliant"
    return score, grade


class Scanner:
    """
    Manages document scanning in a background thread.
    Thread-safe: all callbacks are designed to be wrapped in root.after() by the caller.
    """

    def __init__(self) -> None:
        self._cancel_event = threading.Event()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scanner")
        self._future: Optional[Future] = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def cancel(self) -> None:
        """Signal the background worker to stop."""
        self._cancel_event.set()

    def start_scan(
        self,
        filepath: str,
        enabled_validators: Dict[str, bool],
        on_progress: Callable[[int, str], None],
        on_complete: Callable[[ScanResult], None],
        on_error: Callable[[str], None],
    ) -> None:
        """
        Launch a background scan.

        Parameters
        ----------
        filepath            : path to the PDF or DOCX file
        enabled_validators  : dict mapping validator key → bool
        on_progress         : callback(percent: int, stage: str)
        on_complete         : callback(result: ScanResult)
        on_error            : callback(error_msg: str)
        """
        if self._running:
            return

        self._cancel_event.clear()
        self._running = True

        self._future = self._executor.submit(
            self._run,
            filepath,
            enabled_validators,
            on_progress,
            on_complete,
            on_error,
        )

    def _run(
        self,
        filepath: str,
        enabled_validators: Dict[str, bool],
        on_progress: Callable,
        on_complete: Callable,
        on_error: Callable,
    ) -> None:
        import time
        import json
        import os
        from app.utils.path_helper import get_data_dir

        result = ScanResult()
        start_total = time.perf_counter()
        
        pdf_parse_time_ms = 0.0
        rule_load_time_ms = 0.0
        match_engine_time_ms = 0.0
        total_scan_time_ms = 0.0

        try:
            total_stages = len(STAGES)

            def progress(stage_idx: int, label: str) -> None:
                pct = int((stage_idx / (total_stages - 1)) * 100)
                on_progress(pct, label)

            # Stage 0: Parse
            progress(0, "Parsing Document…")
            ext = filepath.rsplit(".", 1)[-1].lower()
            
            start_parse = time.perf_counter()
            if ext == "pdf":
                doc_data = parse_pdf(filepath, self._cancel_event)
            elif ext in ("docx", "doc"):
                doc_data = parse_docx(filepath, self._cancel_event)
            else:
                raise ValueError(f"Unsupported file type: .{ext}")
            pdf_parse_time_ms = (time.perf_counter() - start_parse) * 1000.0

            result.page_count = doc_data["page_count"]
            result.file_type = ext
            result.filename = filepath

            # Stage 1: Load rules
            progress(1, "Loading Rules…")
            start_rules = time.perf_counter()
            rules = RulesLoader()
            rule_load_time_ms = (time.perf_counter() - start_rules) * 1000.0

            if self._cancel_event.is_set():
                raise ScanCancelledException()

            # Ordered list: (validator_class, stage_index, stage_label)
            validators_to_run = [
                (SectionValidator,      2,  "Checking Required Sections…"),
                (DateValidator,         3,  "Checking Dates…"),
                (VulnerabilityValidator,4,  "Checking Vulnerabilities…"),
                (TerminologyValidator,  5,  "Checking Terminology…"),
                (SpellingValidator,     6,  "Checking Spelling…"),
                (EmptyPageValidator,    7,  "Checking Empty Pages…"),
                (SerialNumberValidator, 8,  "Checking Serial Numbers…"),
                (PageNumberValidator,   9,  "Checking Page Numbers…"),
                (BrandingValidator,     10, "Checking Branding Consistency…"),
            ]

            # Map validator class → rule key in custom_rules.json / enabled_validators dict
            validator_key_map = {
                SectionValidator:       "required_section_validation",
                DateValidator:          "date_validation",
                VulnerabilityValidator: "vulnerability_validation",
                TerminologyValidator:   "terminology_validation",
                SpellingValidator:      "spelling_validation",
                EmptyPageValidator:     "empty_page_validation",
                SerialNumberValidator: "serial_number_validation",
                PageNumberValidator:   "page_number_validation",
                BrandingValidator:     "branding_validation",
            }

            all_findings: List[Finding] = []

            for validator_cls, stage_idx, label in validators_to_run:
                if self._cancel_event.is_set():
                    raise ScanCancelledException()

                key = validator_key_map[validator_cls]
                if key == "page_number_validation":
                    if not enabled_validators.get(key, False):
                        continue
                else:
                    if not enabled_validators.get(key, True):
                        continue

                progress(stage_idx, label)
                
                start_val = time.perf_counter()
                v = validator_cls(self._cancel_event)  # type: ignore
                findings = v.validate(doc_data, rules)
                val_duration_ms = (time.perf_counter() - start_val) * 1000.0
                
                if validator_cls == VulnerabilityValidator:
                    match_engine_time_ms = val_duration_ms
                    
                all_findings.extend(findings)

            # Sort findings by severity order
            all_findings.sort(key=lambda f: f.severity_order)
            result.findings = all_findings

            # Phase 13: Knowledge Discovery
            from app.services.discovery import extract_discovery_candidates
            candidates, summary = extract_discovery_candidates(doc_data, rules)
            result.discovery_candidates = candidates
            result.discovery_summary = summary

            # Calculate score
            progress(11, "Generating Report…")
            result.score, result.grade = _calculate_score(all_findings)
            
            result.branding_summary = doc_data.get("branding_summary", {})
            result.vuln_summary = doc_data.get("vuln_summary", {})

            total_scan_time_ms = (time.perf_counter() - start_total) * 1000.0

            # Write performance metrics
            perf_path = os.path.join(get_data_dir(), "last_scan_performance.json")
            perf_data = {
                "pdf_parse_time_ms": pdf_parse_time_ms,
                "rule_load_time_ms": rule_load_time_ms,
                "match_engine_time_ms": match_engine_time_ms,
                "total_scan_time_ms": total_scan_time_ms,
                "report_export_time_ms": 0.0  # Will be updated by scan_page.py on export
            }
            try:
                with open(perf_path, "w", encoding="utf-8") as pf:
                    json.dump(perf_data, pf, indent=2)
            except Exception:
                pass

            progress(12, "Completed")
            on_complete(result)

        except ScanCancelledException:
            result.cancelled = True
            result.error = "Scan was cancelled."
            on_complete(result)
        except Exception as exc:
            tb = traceback.format_exc()
            on_error(f"{exc}\n\n{tb}")
        finally:
            self._running = False
