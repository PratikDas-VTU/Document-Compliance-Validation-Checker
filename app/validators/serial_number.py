"""
serial_number.py — Validator 7: Serial/List Number Sequence Validation.
Context-aware: resets sequence tracking at section boundaries so that
new sections starting at "1." do not generate false positives.
"""
from __future__ import annotations
import re
import threading
from typing import List, Tuple, Optional
from app.validators.base import BaseValidator, Finding

# Match numbered list items at start of paragraph
_LIST_ITEM_PATTERN = re.compile(r"^\s*(\d+)(?:\.(\d+))?(?:\.(\d+))?\s*[.):\-]\s+\S")

# Section boundary keywords — reset sequence when any of these appear
# Allows optional leading numbering (e.g. "3. Recommendations")
_SECTION_RESET_KEYWORDS = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*\s*[.):\-]?\s*)?(?:solution|solutions|recommendation|recommendations|appendix|appendices"
    r"|procedure|procedures|step|steps|annex|phase|part|chapter|section"
    r"|finding|findings|vulnerability|vulnerabilities|issue|issues"
    r"|background|introduction|overview|summary|scope|methodology"
    r"|conclusion|conclusions|references|bibliography|remediation|remediations)\b",
    re.IGNORECASE,
)

# Also reset when we see a major heading-like paragraph (short, no trailing period)
def _is_section_header(para: str) -> bool:
    """Heuristic: short paragraph that looks like a section title."""
    stripped = para.strip()
    if len(stripped) > 80:
        return False
    if stripped.endswith(".") or stripped.endswith(","):
        return False
    word_count = len(stripped.split())
    if word_count < 1 or word_count > 8:
        return False
    # Check for section reset keywords
    if _SECTION_RESET_KEYWORDS.match(stripped):
        return True
    # All-caps title (e.g., "RECOMMENDATIONS", "APPENDIX A")
    if stripped.isupper() and word_count <= 4:
        return True
    return False


class SerialNumberValidator(BaseValidator):
    name = "Serial Number Validation"

    MAX_FINDINGS = 3

    def validate(self, doc_data: dict, rules_loader) -> List[Finding]:
        self.check_cancel()
        findings: List[Finding] = []

        paragraphs = doc_data["paragraphs"]
        finding_count = 0

        # Track sequences per "context window"
        # Each time we hit a section boundary, we reset
        last_top_num: Optional[int] = None
        context_started = False

        for para_idx, para in enumerate(paragraphs):
            self.check_cancel()
            if finding_count >= self.MAX_FINDINGS:
                break

            # Check for section boundary — reset sequence tracking
            if _is_section_header(para):
                last_top_num = None
                context_started = False
                continue

            # Try to match a numbered list item
            m = _LIST_ITEM_PATTERN.match(para)
            if not m:
                continue

            # Only look at top-level numbers (e.g., "1.", "2.", "3.")
            try:
                num = int(m.group(1))
            except (ValueError, IndexError):
                continue

            if not context_started:
                # First item in this context — start tracking
                context_started = True
                last_top_num = num
                continue

            # Check for sequence break
            # Allow: same number (duplicate), +1 (expected), or reset to 1
            if num == 1:
                # Explicit restart — this is allowed (new sub-list or new context)
                last_top_num = 1
                continue

            expected = (last_top_num or 0) + 1

            if num != expected and num != last_top_num:
                # Only flag if the gap is exactly a skip (e.g. 1,2,4 not 1,2,10)
                # Large jumps are more likely intentional section numbering
                gap = num - (last_top_num or 0)
                if 1 < gap <= 3:
                    findings.append(Finding(
                        severity="Warning",
                        validator=self.name,
                        title=f"List Sequence Break: Found \"{num}\", Expected \"{expected}\"",
                        description=(
                            f"A numbered list near paragraph {para_idx + 1} has a sequence break. "
                            f"Found item \"{num}\" but expected \"{expected}\"."
                        ),
                        location=f"Paragraph {para_idx + 1}: \"{para[:60].strip()}\"",
                        recommendation=(
                            "Review the numbered list for missing or duplicate items. "
                            "Ensure sequential numbering within each section."
                        ),
                    ))
                    finding_count += 1

            last_top_num = num

        return findings
