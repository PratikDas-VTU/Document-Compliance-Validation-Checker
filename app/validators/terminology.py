"""
terminology.py — Validator 4: Terminology / Acronym Definition Validation.
Checks that non-universal acronyms are defined on first use.

Major improvements:
- Comprehensive report stopword list (section headers, severity labels, metadata)
- Asset/hostname pattern detection (SW01, RTR02, SYN-S15-FF-SW01)
- Only flags acronyms used 3+ times without definition (reduces noise)
- Universal common acronyms are exempt
"""
from __future__ import annotations
import re
import threading
from typing import List, Set, Dict
from app.validators.base import BaseValidator, Finding

# ── Universal acronyms — NEVER require a definition ───────────────────────────
UNIVERSAL_ACRONYMS: Set[str] = {
    "TCP", "UDP", "DNS", "HTTP", "HTTPS", "SSH", "FTP", "SMTP",
    "OSI", "IP", "MAC", "VLAN", "VPN", "ACL", "NAT", "LAN", "WAN",
    "ICMP", "ARP", "BGP", "OSPF", "RIP", "MPLS", "QOS",
    "XML", "JSON", "HTML", "CSS", "URL", "URI", "API", "SDK", "GUI",
    "CPU", "GPU", "RAM", "ROM", "OS", "PC", "USB", "SSD", "HDD",
    "PDF", "DOC", "DOCX", "XLS", "PPT", "ZIP", "ISO", "EXE",
    "AD", "DC", "OU", "GPO", "MDM", "UPS", "NTP", "SNMP", "LDAP",
    "TLS", "SSL", "RSA", "AES", "SHA", "MD5", "OTP", "MFA", "2FA",
    "SQL", "DB", "CI", "CD", "VM", "SaaS", "PaaS", "IaaS",
    "AWS", "GCP", "IoT", "AI", "ML", "NLP", "CLI", "GUI",
    "CVE", "CVSS", "NVD", "NIST", "ISO", "RFC",
    "XSS", "SQLI", "CSRF", "SSRF", "RCE", "LFI", "RFI",
    "IDS", "IPS", "SOC", "SIEM", "WAF", "UTM", "DMZ",
    "PKI", "CA", "CRL", "OCSP",
}

# ── Report structure / metadata stopwords — NEVER flag these ─────────────────
REPORT_STOPWORDS: Set[str] = {
    # Document structure
    "REPORT", "SUMMARY", "DOCUMENT", "SECTION", "CATEGORY", "DESCRIPTION",
    "TITLE", "TABLE", "FIGURE", "APPENDIX", "ANNEX", "CHAPTER", "PART",
    "PAGE", "CONTENTS", "INDEX", "GLOSSARY", "REFERENCE", "REFERENCES",
    "BIBLIOGRAPHY", "INTRODUCTION", "OVERVIEW", "BACKGROUND", "FOREWORD",
    "PREFACE", "ABSTRACT", "SCOPE", "METHODOLOGY", "APPROACH",
    "CONCLUSION", "CONCLUSIONS", "DISCLAIMER",

    # Advice / action words
    "ADVICE", "SOLUTION", "SOLUTIONS", "RECOMMENDATION", "RECOMMENDATIONS",
    "FINDING", "FINDINGS", "REVIEW", "ASSESSMENT", "AUDIT", "EVALUATION",
    "REMEDIATION", "MITIGATION", "OBSERVATION", "OBSERVATIONS",
    "ISSUE", "ISSUES", "VULNERABILITY", "VULNERABILITIES", "RISK", "RISKS",

    # Severity / status labels
    "HIGH", "MEDIUM", "LOW", "CRITICAL", "WARNING", "INFO", "INFORMATION",
    "INFORMATIONAL", "SEVERE", "MODERATE", "MINOR", "MAJOR", "NONE",
    "PASS", "FAIL", "PASSED", "FAILED", "ERROR", "SUCCESS",
    "OPEN", "CLOSED", "RESOLVED", "PENDING", "ACCEPTED", "REJECTED",

    # Network / infrastructure terms that appear as ALL-CAPS headings
    "CONFIGURATION", "SWITCH", "ROUTER", "SERVER", "CLIENT", "HOST",
    "NETWORK", "SYSTEM", "SECURITY", "FIREWALL", "GATEWAY", "PROXY",
    "PATCH", "UPDATE", "VERSION", "RELEASE",

    # Report metadata
    "NAME", "DATE", "TIME", "VERSION", "STATUS", "AUTHOR", "OWNER",
    "PRIORITY", "TYPE", "CLASS", "LEVEL", "SCORE", "RATING", "GRADE",
    "RESULT", "NOTE", "NOTES", "COMMENT", "COMMENTS", "REMARKS",
    "REFERENCE", "ID", "REF",

    # Testing/actions
    "TEST", "TESTING", "SCAN", "CHECK", "VERIFY", "VALIDATE", "CONFIRM",
    "ENABLE", "DISABLE", "ALLOW", "DENY", "BLOCK", "PERMIT",
    "APPLY", "IMPLEMENT", "ENFORCE", "REVIEW", "ANALYSIS", "IMPACT",

    # Common words in ALL-CAPS in tables
    "YES", "NO", "TRUE", "FALSE", "NULL", "OTHER", "ALL", "ANY", "NONE",
    "APPLICABLE", "REQUIRED", "OPTIONAL", "MANDATORY", "RECOMMENDED",
    "DEFAULT", "CUSTOM", "MANUAL", "AUTOMATIC", "ENABLED", "DISABLED",

    # Report sections used in cybersec reports
    "EXECUTIVE", "TECHNICAL", "MANAGEMENT", "OPERATIONAL",
    "INTERNAL", "EXTERNAL", "PHYSICAL", "LOGICAL", "VIRTUAL",
}

# ── Asset/hostname patterns — these are identifiers, not acronyms ─────────────
_ASSET_PATTERNS = [
    re.compile(r'^[A-Z]{1,5}\d+[A-Z]?$'),              # SW01, S15, RTR02, B03, S15A
    re.compile(r'^[A-Z]+-[A-Z0-9]+-[A-Z0-9-]+$'),      # SYN-S15-FF-SW01, HOST-01
    re.compile(r'^[A-Z]+[-_]\d+$'),                      # SERVER-01, RACK_01
    re.compile(r'^[A-Z]{2,6}\d{2,}$'),                  # SW01, RTR002, FIREWALL01
    re.compile(r'^[A-Z]+[0-9]+[A-Z]+[0-9]+$'),          # SW01FF02 (mixed)
]

# ── Acronym detection patterns ────────────────────────────────────────────────
# True acronym: 2–30 uppercase letters (optionally with digits, hyphens, underscores for hostnames)
_ACRONYM_PATTERN = re.compile(r'\b([A-Z0-9\-_]{2,30})\b')

# Definition pattern: "Full Name (ACRONYM)" or "ACRONYM (Full Name)"
_DEFINITION_PATTERN = re.compile(
    r'\b[A-Z][a-z]+(?:\s+[A-Z]?[a-z]+){1,8}\s+\(([A-Z][A-Z0-9]{1,7})\)'
    r'|([A-Z][A-Z0-9]{1,7})\s+\([A-Za-z][a-z]+(?:\s+[a-z]+){1,8}\)',
    re.MULTILINE,
)


def _is_asset_identifier(token: str) -> bool:
    """Return True if the token looks like an asset name or hostname."""
    return any(p.match(token) for p in _ASSET_PATTERNS)


def _is_common_english_word(token: str) -> bool:
    """Return True if this looks like a common English word in all-caps (not an acronym)."""
    # Words longer than 8 chars in all-caps are almost certainly section headings, not acronyms
    if len(token) > 8:
        return True
    return False


class TerminologyValidator(BaseValidator):
    name = "Terminology Validation"

    # Only flag acronyms used this many times or more without definition
    MIN_OCCURRENCES = 3
    MAX_FINDINGS = 8

    def validate(self, doc_data: dict, rules_loader) -> List[Finding]:
        self.check_cancel()
        findings: List[Finding] = []
        full_text = doc_data["full_text"]
        known_acronyms: Dict[str, str] = {
            k.upper(): v for k, v in rules_loader.acronyms.items()
        }

        # Find all acronyms that have a parenthetical definition in the text
        defined_in_text: Set[str] = set()
        for m in _DEFINITION_PATTERN.finditer(full_text):
            acronym = (m.group(1) or m.group(2) or "").upper()
            if acronym:
                defined_in_text.add(acronym)

        # Also add all acronyms that appear with a dash-separated definition
        # e.g., "SSRF - Server-Side Request Forgery"
        _dash_def = re.compile(
            r'\b([A-Z]{2,8})\s+[-–]\s+[A-Z][a-z]+(?:\s+[A-Za-z-]+){1,8}'
        )
        for m in _dash_def.finditer(full_text):
            defined_in_text.add(m.group(1).upper())

        seen: Set[str] = set()
        finding_count = 0

        for m in _ACRONYM_PATTERN.finditer(full_text):
            self.check_cancel()
            if finding_count >= self.MAX_FINDINGS:
                break

            acronym = m.group(1).upper()

            if acronym in seen:
                continue
            seen.add(acronym)

            if not any(c.isalpha() for c in acronym):
                continue

            # ── Filtering pipeline ────────────────────────────────────────
            # 1. Skip universal acronyms
            if acronym in UNIVERSAL_ACRONYMS:
                continue

            # 2. Skip report structural stopwords
            if acronym in REPORT_STOPWORDS:
                continue

            # 3. Skip asset/hostname identifiers
            if _is_asset_identifier(acronym):
                continue

            # 4. Skip if looks like a common English word in caps or exists in dictionary
            if _is_common_english_word(acronym) or acronym.lower() in rules_loader.standard_english:
                continue

            # 5. Skip if defined in the document
            if acronym in defined_in_text:
                continue

            # 6. Skip if it's in the acronyms.json dictionary
            if acronym in known_acronyms:
                continue

            # 7. Skip if too short (single letters, 2-letter common abbrevs)
            if len(acronym) < 3:
                continue

            # 8. Only flag if the acronym appears multiple times (reduces noise)
            occurrences = len(re.findall(r'\b' + re.escape(acronym) + r'\b', full_text))
            if occurrences < self.MIN_OCCURRENCES:
                continue

            findings.append(Finding(
                severity="Information",
                validator=self.name,
                title=f"Undefined Acronym: \"{acronym}\"",
                description=(
                    f"The acronym \"{acronym}\" appears {occurrences} time(s) in the document "
                    "but is not defined on first use."
                ),
                location="Document-wide",
                recommendation=(
                    f"Define \"{acronym}\" on its first occurrence using the format: "
                    f"\"Full Name ({acronym})\"."
                ),
            ))
            finding_count += 1

        return findings
