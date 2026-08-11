"""
sections.py — Validator 1: Required Section Validation.
Checks that all required headings/sections defined in required_sections.json
are present anywhere in the document text (case-insensitive).
Supports section aliases via section_aliases.json for flexible matching.
"""
from __future__ import annotations
import threading
from typing import List, Dict, Set
from app.validators.base import BaseValidator, Finding


class SectionValidator(BaseValidator):
    name = "Required Section Validation"

    def validate(self, doc_data: dict, rules_loader) -> List[Finding]:
        self.check_cancel()
        findings: List[Finding] = []
        full_text_lower = doc_data["full_text"].lower()
        required = rules_loader.required_sections
        aliases: Dict[str, List[str]] = rules_loader.section_aliases

        for section in required:
            self.check_cancel()
            # Build the full set of accepted names: canonical + all aliases
            accepted_names: List[str] = [section]
            if section in aliases:
                accepted_names.extend(aliases[section])

            # Check if any accepted name appears in the document
            found = any(name.lower() in full_text_lower for name in accepted_names)

            if not found:
                alias_hint = ""
                if section in aliases and aliases[section]:
                    alias_hint = f" (also accepted: {', '.join(aliases[section][:3])})"

                findings.append(Finding(
                    severity="Critical",
                    validator=self.name,
                    title=f"Missing Required Section: \"{section}\"",
                    description=(
                        f"The document does not contain a section titled \"{section}\""
                        f"{alias_hint}. This section is mandatory for compliant documents."
                    ),
                    location="Document Structure",
                    recommendation=(
                        f"Add a clearly labelled \"{section}\" section to the document "
                        "with appropriate content. Equivalent headings are also accepted."
                    ),
                ))

        return findings
