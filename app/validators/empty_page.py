"""
empty_page.py — Validator 6: Empty Page Validation.
A page is considered empty only when it has fewer than 5 meaningful words.
Avoids false positives on cover, diagram, appendix, and figure pages.
"""
from __future__ import annotations
import re
import threading
from typing import List
from app.validators.base import BaseValidator, Finding

# Words that don't count as "meaningful" content
_NOISE_WORDS = {
    "page", "of", "the", "a", "an", "this", "is", "and", "or", "for",
    "in", "on", "at", "to", "by", "with", "from", "that", "it",
    "figure", "table", "appendix", "annex", "exhibit", "diagram",
    "continued", "cont", "see", "above", "below", "ref", "note",
}

# Meaningful word: at least 3 chars, purely alphabetic
_WORD_PATTERN = re.compile(r"\b[a-zA-Z]{3,}\b")


def _count_meaningful_words(text: str) -> int:
    words = _WORD_PATTERN.findall(text.lower())
    return sum(1 for w in words if w not in _NOISE_WORDS)


class EmptyPageValidator(BaseValidator):
    name = "Empty Page Validation"

    MEANINGFUL_WORD_THRESHOLD = 5

    def validate(self, doc_data: dict, rules_loader) -> List[Finding]:
        self.check_cancel()
        findings: List[Finding] = []

        for page in doc_data["pages"]:
            self.check_cancel()
            page_num = page["page_num"]
            text = page["text"]
            meaningful = _count_meaningful_words(text)

            if meaningful < self.MEANINGFUL_WORD_THRESHOLD:
                findings.append(Finding(
                    severity="Critical",
                    validator=self.name,
                    title=f"Empty or Near-Empty Page Detected (Page {page_num})",
                    description=(
                        f"Page {page_num} contains only {meaningful} meaningful word(s), "
                        f"which is below the threshold of {self.MEANINGFUL_WORD_THRESHOLD}. "
                        "The page appears to have insufficient content."
                    ),
                    location=f"Page {page_num}",
                    recommendation=(
                        "Review Page " + str(page_num) + ". If it is intentional (e.g., cover "
                        "page, divider, diagram), this finding can be dismissed. "
                        "Otherwise, populate the page with appropriate content."
                    ),
                ))

        return findings
