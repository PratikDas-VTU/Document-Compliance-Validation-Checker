"""
date.py — Validator 2: Date Format Validation.
Extracts date-like strings from document text and verifies they conform to
allowed formats defined in format_rules.json.
"""
from __future__ import annotations
import re
import threading
from typing import List, Tuple
from app.validators.base import BaseValidator, Finding

# Regex patterns for date detection
_DATE_PATTERNS = [
    # DD/MM/YYYY or MM/DD/YYYY
    re.compile(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b"),
    # YYYY-MM-DD (ISO)
    re.compile(r"\b(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})\b"),
    # DD-MMM-YYYY  e.g.  13-Jun-2025
    re.compile(r"\b(\d{1,2})[-\s]([A-Za-z]{3,9})[-\s](\d{4})\b"),
    # MMM DD, YYYY  e.g.  June 13, 2025
    re.compile(r"\b([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})\b"),
]

_MONTH_NAMES = {
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec",
    "january", "february", "march", "april", "june",
    "july", "august", "september", "october", "november", "december",
}

_AMBIGUOUS_PATTERN = re.compile(r"\b(\d{1,2})[/](\d{1,2})[/](\d{4})\b")


def _validate_date_components(year: int, month: int, day: int) -> bool:
    """Return True if the date components represent a plausible calendar date."""
    import calendar
    if not (1900 <= year <= 2100):
        return False
    if not (1 <= month <= 12):
        return False
    max_day = calendar.monthrange(year, month)[1]
    return 1 <= day <= max_day


def _extract_dates(text: str) -> List[Tuple[str, int, int, int]]:
    """Extract dates and return list of (matched_str, year, month, day)."""
    results = []
    seen = set()

    for pattern in _DATE_PATTERNS:
        for m in pattern.finditer(text):
            raw = m.group(0)
            if raw in seen:
                continue
            seen.add(raw)
            groups = m.groups()
            try:
                if len(groups) == 3:
                    g0, g1, g2 = groups
                    # YYYY-MM-DD
                    if len(g0) == 4 and g0.isdigit():
                        y, mo, d = int(g0), int(g1), int(g2)
                    # DD-MMM-YYYY or MMM DD YYYY
                    elif g0.isalpha() or g1.isalpha() or (len(g2) == 4 and g2.isdigit()):
                        if g0.isalpha() and g0.lower() in _MONTH_NAMES:
                            # MMM DD YYYY
                            import datetime
                            import calendar
                            mo = list(_MONTH_NAMES).index(g0.lower()[:3]) % 12 + 1
                            d, y = int(g1), int(g2)
                        elif g1.isalpha() and g1.lower()[:3] in _MONTH_NAMES:
                            # DD-MMM-YYYY
                            month_map = {m: i+1 for i, m in enumerate(
                                ["jan","feb","mar","apr","may","jun",
                                 "jul","aug","sep","oct","nov","dec"])}
                            d = int(g0)
                            mo = month_map.get(g1.lower()[:3], 0)
                            y = int(g2)
                        else:
                            # DD/MM/YYYY ambiguous
                            d, mo, y = int(g0), int(g1), int(g2)
                    else:
                        d, mo, y = int(g0), int(g1), int(g2)

                    if not _validate_date_components(y, mo, d):
                        results.append((raw, -1, -1, -1))  # invalid date
                    else:
                        results.append((raw, y, mo, d))
            except (ValueError, IndexError):
                continue

    return results


class DateValidator(BaseValidator):
    name = "Date Validation"

    def validate(self, doc_data: dict, rules_loader) -> List[Finding]:
        self.check_cancel()
        findings: List[Finding] = []
        seen_issues: set = set()

        for para in doc_data["paragraphs"]:
            self.check_cancel()
            dates = _extract_dates(para)
            for raw, y, mo, d in dates:
                if raw in seen_issues:
                    continue
                if y == -1:  # invalid calendar date
                    seen_issues.add(raw)
                    findings.append(Finding(
                        severity="Warning",
                        validator=self.name,
                        title=f"Invalid Date: \"{raw}\"",
                        description=f"The date \"{raw}\" does not represent a valid calendar date.",
                        location=f"Near: \"{para[:60].strip()}...\"" if len(para) > 60 else para.strip(),
                        recommendation="Verify and correct the date to a valid calendar value.",
                    ))

        return findings
