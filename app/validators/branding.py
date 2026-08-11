"""
branding.py — Validator 9: Branding Consistency Validation.
Detects when the document references one organization in the text but contains
logos belonging to another organization.
"""
from __future__ import annotations
import threading
import time
from typing import List, Dict, Any
from app.validators.base import BaseValidator, Finding
from app.services.branding_engine import BrandingEngine

class BrandingValidator(BaseValidator):
    name = "Branding Consistency Validation"

    def validate(self, doc_data: dict, rules_loader) -> List[Finding]:
        self.check_cancel()
        findings: List[Finding] = []
        
        # 1. Initialize engine
        engine = BrandingEngine()
        if not engine.logo_db and engine.status == "Initializing":
            # Wait up to 2 seconds for background thread to load fingerprints
            for _ in range(20):
                if engine.status != "Initializing":
                    break
                time.sleep(0.1)
        
        if not engine.logo_db:
            # Fallback: load synchronously
            engine.initialize_engine()
            
        org_names = list(engine.logo_db.keys())
        if not org_names:
            return findings # No logos loaded to match against
            
        full_text = doc_data.get("full_text", "")
        pages = doc_data.get("pages", [])
        paragraphs = doc_data.get("paragraphs", [])
        full_text_lower = full_text.lower()
        
        # ── Phase 1: Determine Primary Organization (Weighted Discovery) ──
        scores = {org: 0 for org in org_names}
        
        for org in org_names:
            self.check_cancel()
            org_lower = org.lower()
            
            # Count standard body references
            scores[org] = full_text_lower.count(org_lower)
            
            # Cover Page scoring
            if pages:
                p1_text = pages[0].get("text", "")
                p1_text_lower = p1_text.lower()
                if org_lower in p1_text_lower:
                    # Check if it's in the very top of the page (Cover Page Title)
                    if org_lower in p1_text_lower[:250]:
                        scores[org] += 10
                    else:
                        scores[org] += 5
                        
                    # Client Name / Prepared For scoring
                    idx = p1_text_lower.find(org_lower)
                    start = max(0, idx - 80)
                    end = min(len(p1_text_lower), idx + len(org_lower) + 80)
                    context = p1_text_lower[start:end]
                    client_keywords = ["prepared for", "client", "submitted to", "prepared by", "compiled for", "assessment for"]
                    if any(kw in context for kw in client_keywords):
                        scores[org] += 8

            # Main Report Title (usually page 1 or page 2 heading)
            if len(pages) > 1:
                p2_text_lower = pages[1].get("text", "").lower()
                if org_lower in p2_text_lower[:200]:
                    scores[org] += 10
                    
            # Executive Summary scoring
            for para in paragraphs:
                para_lower = para.lower()
                if "executive summary" in para_lower or "executive overview" in para_lower or "summary of findings" in para_lower:
                    if org_lower in para_lower:
                        scores[org] += 5
                        
            # Headers / Footers scoring (top/bottom margins on pages 2+)
            for page in pages[1:]:
                p_text = page.get("text", "")
                p_text_lower = p_text.lower()
                if org_lower in p_text_lower:
                    if org_lower in p_text_lower[:120] or org_lower in p_text_lower[-120:]:
                        scores[org] += 4

        # Find org with highest score
        best_org = None
        best_score = 0
        for org, score in scores.items():
            if score > best_score:
                best_score = score
                best_org = org
                
        # Primary Organization must have a minimum weighted score threshold
        primary_org = best_org if best_score >= 3 else "Unknown"
        
        # ── Phase 2 & 3: Logo Extraction and Match Recognition ──
        # Track matches by organization name
        # structure: {org_name: [{"page": page, "confidence": conf}, ...]}
        detected_logos: Dict[str, List[Dict[str, Any]]] = {}
        images = doc_data.get("images", [])
        engine.total_images_analyzed += len(images)
        
        for img in images:
            self.check_cancel()
            page_num = img.get("page_num", 1)
            img_bytes = img.get("image_bytes", b"")
            
            if not img_bytes:
                continue
                
            matched_org, match_conf = engine.match_image(img_bytes)
            if matched_org:
                if matched_org not in detected_logos:
                    detected_logos[matched_org] = []
                detected_logos[matched_org].append({
                    "page": page_num,
                    "confidence": match_conf
                })

        # ── Phase 4: Consistency Analysis & False Positive Protection ──
        # Generate findings for any detected logo that does not match primary_org
        for logo_org, sightings in detected_logos.items():
            self.check_cancel()
            if primary_org != "Unknown" and logo_org == primary_org:
                continue # Consistent branding
                
            # Compute average matching confidence for this logo
            avg_logo_conf = sum(s["confidence"] for s in sightings) / len(sightings)
            
            # Violation Confidence calculation
            violation_conf = avg_logo_conf
            
            # If the logo's organization is mentioned in the text, it might be a partner/preparer
            if scores.get(logo_org, 0) > 0:
                logo_org_lower = logo_org.lower()
                idx = full_text_lower.find(logo_org_lower)
                start = max(0, idx - 100)
                end = min(len(full_text_lower), idx + len(logo_org_lower) + 100)
                context = full_text_lower[start:end]
                preparer_keywords = ["prepared by", "by:", "assessed by", "consultant", "vendor", "partner", "association"]
                if any(pw in context for pw in preparer_keywords):
                    violation_conf -= 20 # decrease confidence since it's a preparer/vendor
                else:
                    violation_conf -= 10
            else:
                # Not mentioned in text at all, highly suspicious!
                violation_conf += 5
                
            violation_conf = min(99.0, max(0.0, violation_conf))
            
            # Threshold to generate finding
            if violation_conf < 40.0:
                continue
                
            engine.total_mismatches_found += 1
            
            # Determine Severity
            # Confidence >= 80% -> Critical (HIGH)
            # Confidence >= 60% and < 80% -> Warning
            # Confidence >= 40% and < 60% -> Information
            if violation_conf >= 80.0:
                severity = "Critical"
            elif violation_conf >= 60.0:
                severity = "Warning"
            else:
                severity = "Information"
                
            # Create page-level evidence text block
            evidence_lines = []
            for s in sightings:
                evidence_lines.append(f"Page {s['page']} \u2192 {logo_org} ({int(s['confidence'])}%)")
            evidence_str = "\n".join(evidence_lines)
            
            finding_loc = f"Page {sightings[0]['page']}"
            if len(sightings) > 1:
                finding_loc += f" (and {len(sightings)-1} other pages)"
                
            why_finding = (
                f"Primary organization identified as {primary_org}.\n\n"
                f"Visual branding detected as {logo_org}.\n\n"
                f"These organizations do not match."
            )
            
            desc_text = (
                f"Expected:\n{primary_org}\n\n"
                f"Detected:\n{logo_org}\n\n"
                f"Page:\n{sightings[0]['page']}"
            )
            
            details_payload = {
                "expected_org": primary_org,
                "detected_logo": logo_org,
                "confidence": int(violation_conf),
                "evidence_list": sightings,
                "why_finding": why_finding
            }
            
            findings.append(Finding(
                severity=severity,
                validator=self.name,
                title="Branding Consistency Violation",
                description=desc_text,
                location=finding_loc,
                recommendation="Review document branding and replace outdated organization assets.",
                details=details_payload
            ))
            
        total_logos = sum(len(sightings) for sightings in detected_logos.values())
        pages_containing_logos = len({s["page"] for sightings in detected_logos.values() for s in sightings})
        consistency_score = 100.0 if total_logos == 0 else max(0.0, ((total_logos - len(findings)) / total_logos) * 100.0)
        
        doc_data["branding_summary"] = {
            "primary_org": primary_org,
            "logo_present": total_logos > 0,
            "total_logos": total_logos,
            "detected_orgs": list(detected_logos.keys()),
            "brand_consistency": "Failed" if findings else "Matched",
            "consistency_score": consistency_score,
            "pages_containing_logos": pages_containing_logos,
            "status": "Failed" if findings else ("Pass" if primary_org != "Unknown" and total_logos > 0 else "N/A")
        }
            
        return findings
