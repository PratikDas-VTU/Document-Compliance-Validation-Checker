"""
spelling.py — Validator 5: Spelling Validation.
Uses pyspellchecker (87,000+ word English dictionary) as the primary source.
Supplements with all domain-specific whitelists.
Detects CLI/config blocks and skips them entirely.
Aggressively filters noise to keep findings actionable.
"""
from __future__ import annotations
import re
import threading
from typing import List, Set
from app.validators.base import BaseValidator, Finding

# ── Spell checker (lazy-loaded singleton) ─────────────────────────────────────
_spell_checker = None

def _get_spell_checker():
    global _spell_checker
    if _spell_checker is None:
        try:
            from spellchecker import SpellChecker
            _spell_checker = SpellChecker()
        except Exception:
            _spell_checker = None
    return _spell_checker


# ── Words to never flag ───────────────────────────────────────────────────────
_ALWAYS_SKIP: Set[str] = {
    "i", "a", "ii", "iii", "iv", "vi", "vii", "viii", "ix", "xi", "xii",
    "eg", "ie", "etc", "vs", "nb", "re", "cc", "ok", "pdf", "csv",
}

# ── CLI/config detection patterns ─────────────────────────────────────────────
_CLI_PATTERNS = [
    re.compile(r"^[\$#>]\s+\S"),
    re.compile(r"^[A-Za-z0-9\-]+[>#]\s"),
    re.compile(r"^\s*(sudo|chmod|chown|systemctl|service|apt|yum|dnf|pip|npm|git)\s"),
    re.compile(r"^\s*(Get-|Set-|Invoke-|New-|Remove-|Start-|Stop-|Add-|Clear-)[A-Z]"),
    re.compile(r"^\s*(ip\s+address|no\s+shutdown|interface\s+\w|router\s+\w|spanning-tree)"),
    re.compile(r"^\s*show\s+(running|version|interfaces|ip\s+route)"),
    re.compile(r"C:\\[A-Za-z]"),
    re.compile(r"^\s*[A-Za-z0-9_\-]+\s*=\s*['\"\{]"),
    re.compile(r"^\s*(nmap|metasploit|sqlmap|nikto|wireshark|tcpdump)\s"),
]

# ── Token-level skip patterns ─────────────────────────────────────────────────
_SKIP_TOKEN_PATTERN = re.compile(
    r"https?://|www\.|@"
    r"|\.(com|org|net|io|gov|edu|co|uk|au)\b"
    r"|[A-Z][a-z]+[A-Z]"        # camelCase
    r"|[A-Z]{2,}"               # ALL-CAPS acronym/heading
    r"|\d"                       # contains digit
    r"|[_\-]{2,}"               # double underscore/dash
    r"|[\\\/]"                  # path separators
    r"|<[^>]+>"                 # XML/HTML tags
)

# Word extraction: only plain lowercase words 3+ chars
_WORD_PATTERN = re.compile(r"\b[a-z]{3,}\b")


def _is_cli_block(text: str) -> bool:
    lines = text.strip().splitlines()
    if not lines:
        return False
    cli_count = sum(
        1 for line in lines[:15]
        if any(p.search(line) for p in _CLI_PATTERNS)
    )
    return cli_count >= max(1, len(lines[:15]) * 0.25)


def _is_known_word(word: str, whitelist: Set[str], spell) -> bool:
    """Return True if the word is acceptable (in whitelist or spell checker dict)."""
    if word in whitelist:
        return True
    if spell is not None:
        # pyspellchecker: unknown() returns words NOT in dictionary
        return not bool(spell.unknown([word]))
    return False


class SpellingValidator(BaseValidator):
    name = "Spelling Validation"

    MAX_FINDINGS = 6

    def validate(self, doc_data: dict, rules_loader) -> List[Finding]:
        self.check_cancel()
        findings: List[Finding] = []
        whitelist: Set[str] = rules_loader.spelling_whitelist
        spell = _get_spell_checker()
        seen_words: Set[str] = set()
        finding_count = 0

        for para in doc_data["paragraphs"]:
            self.check_cancel()

            if finding_count >= self.MAX_FINDINGS:
                break

            # Skip CLI/config blocks entirely
            if _is_cli_block(para):
                continue

            # Skip very short paragraphs (headers, labels, page numbers)
            stripped_words = para.split()
            if len(stripped_words) < 4:
                continue

            # Work only with the lowercase version for matching
            para_lower = para.lower()

            for word in _WORD_PATTERN.findall(para_lower):
                self.check_cancel()
                if finding_count >= self.MAX_FINDINGS:
                    break

                # Already evaluated
                if word in seen_words:
                    continue

                # Never-flag list
                if word in _ALWAYS_SKIP:
                    continue

                seen_words.add(word)

                # Skip known words
                if _is_known_word(word, whitelist, spell):
                    continue

                # Unknown — generate finding
                findings.append(Finding(
                    severity="Warning",
                    validator=self.name,
                    title=f"Unrecognised Word: \"{word}\"",
                    description=(
                        f"The word \"{word}\" was not found in the English dictionary "
                        "or any approved term list. This may be a spelling error."
                    ),
                    location=f"Near: \"{para[:80].strip()}\"",
                    recommendation=(
                        f"Verify the spelling of \"{word}\". If it is an approved term "
                        "or proper noun, add it to rules/whitelist.json."
                    ),
                ))
                finding_count += 1

        return findings
