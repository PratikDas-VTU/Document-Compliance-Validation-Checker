"""
base.py — BaseValidator and Finding dataclasses.
All validators inherit from BaseValidator and check cancel_event before heavy loops.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
import threading


@dataclass
class Finding:
    """Represents a single validation finding."""
    severity: str          # "Critical" | "Warning" | "Information"
    validator: str         # Human-readable validator name
    title: str             # Short summary
    description: str       # Detailed description
    location: str          # e.g. "Page 3" or "Paragraph 12"
    recommendation: str    # Actionable fix

    # Match Quality fields (Phase 5E)
    match_quality: str = ""
    confidence_score: int = 0
    matched_vulnerability: str = ""
    description_alignment: str = ""
    remediation_alignment: str = ""
    severity_alignment: str = ""
    suggested_category: str = ""
    extracted_keywords: List[str] = field(default_factory=list)
    why_matched: List[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)

    # Explainability fields (Phase 5G)
    match_score_breakdown: dict = field(default_factory=dict)
    match_evidence: dict = field(default_factory=dict)
    missing_evidence: dict = field(default_factory=dict)
    top_candidates: List[dict] = field(default_factory=list)

    @property
    def severity_order(self) -> int:
        return {"Critical": 0, "Warning": 1, "Information": 2}.get(self.severity, 3)


class ScanCancelledException(Exception):
    """Raised when the user requests scan cancellation."""
    pass


class BaseValidator:
    """
    Base class for all validators.
    Subclasses implement `validate(doc_data, rules_loader)` and return List[Finding].
    """

    name: str = "BaseValidator"

    def __init__(self, cancel_event: threading.Event) -> None:
        self.cancel_event = cancel_event

    def check_cancel(self) -> None:
        """Raise ScanCancelledException if cancellation has been requested."""
        if self.cancel_event.is_set():
            raise ScanCancelledException("Scan cancelled by user.")

    def validate(self, doc_data: dict, rules_loader) -> List[Finding]:
        raise NotImplementedError
