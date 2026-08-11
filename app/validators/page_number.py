"""
page_number.py — Validator 8: Page Number Validation (DISABLED BY DEFAULT).
Checks that visible page numbers on pages are sequential.
Many PDFs render page numbers as images or in footers that are hard to extract,
so this validator is opt-in only.
"""
from __future__ import annotations
import re
import threading
from typing import List
from app.validators.base import BaseValidator, Finding

# Look for isolated numbers that could be page numbers
_PAGE_NUM_PATTERN = re.compile(r"(?:^|\n)\s*(\d{1,4})\s*(?:\n|$)")


class PageNumberValidator(BaseValidator):
    name = "Page Number Validation"

    def validate(self, doc_data: dict, rules_loader) -> List[Finding]:
        self.check_cancel()
        findings: List[Finding] = []
        pages = doc_data["pages"]

        if len(pages) < 2:
            return findings

        # Try to detect page numbers from the beginning or end of each page text
        detected: List[tuple] = []  # (page_num, detected_number)

        for page in pages:
            self.check_cancel()
            text = page["text"].strip()
            if not text:
                continue

            # Check first and last 200 characters for page number patterns
            sample = text[:200] + "\n" + text[-200:]
            nums = _PAGE_NUM_PATTERN.findall(sample)

            # Filter to numbers close to the actual page number
            page_num = page["page_num"]
            candidates = [int(n) for n in nums if abs(int(n) - page_num) <= 5]

            if candidates:
                detected.append((page_num, candidates[0]))

        if len(detected) < 3:
            # Not enough evidence to validate
            return findings

        # Check sequence
        for i in range(1, len(detected)):
            self.check_cancel()
            prev_pg, prev_num = detected[i - 1]
            curr_pg, curr_num = detected[i]

            if curr_num != prev_num + 1 and abs(curr_pg - prev_pg) == 1:
                findings.append(Finding(
                    severity="Warning",
                    validator=self.name,
                    title=f"Page Number Sequence Break at Page {curr_pg}",
                    description=(
                        f"Page {curr_pg} appears to show number \"{curr_num}\" "
                        f"but the expected sequential number was \"{prev_num + 1}\"."
                    ),
                    location=f"Page {curr_pg}",
                    recommendation=(
                        "Review page numbering. Ensure all pages are numbered sequentially "
                        "starting from page 1 (or from the first content page)."
                    ),
                ))
                if len(findings) >= 2:
                    break

        return findings
