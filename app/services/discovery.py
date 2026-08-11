import re
from typing import Dict, List, Set, Tuple

def extract_discovery_candidates(doc_data: Dict, rules_loader) -> Tuple[List[Dict], Dict]:
    """
    Scans the document paragraphs and extracts potential new knowledge.
    Filters out numeric noise, rule IDs, and OCR fragments, then scores confidence.
    Returns: (eligible_candidates_list, summary_dict)
    """
    candidates = {}
    paragraphs = doc_data.get("paragraphs", [])
    
    branding_orgs = set(doc_data.get("branding_summary", {}).get("detected_orgs", []))
    
    # Generic blocklist
    GENERIC_WORDS = {
        "REPORT", "REFERENCE", "TITLE", "OBSERVATION", "ASSESSMENT",
        "RECOMMENDATION", "SUMMARY", "DETAILED", "OF", "OR", "THE",
        "AND", "TO", "IN", "IS", "ON", "FOR", "WITH", "BY", "THIS",
        "THAT", "FROM", "AS", "AT", "AN", "IT", "BE", "ARE", "WAS", "WERE",
        "PAGE", "PARAGRAPH", "DATE", "VERSION", "STATUS", "GRADE", "SCORE"
    }

    # Context keywords
    ORG_KEYWORDS = {"company", "organization", "vendor", "client", "partner", "solutions", "technologies", "tech", "systems", "pvt", "ltd", "inc", "corp"}
    PRODUCT_KEYWORDS = {"product", "platform", "suite", "tool", "appliance", "gateway", "scanner", "dashboard", "version", "v"}
    
    # Pre-compile regexes
    # Acronyms: 2-10 uppercase letters only (digits/special characters are not allowed for clean acronyms)
    acronym_pattern = re.compile(r"\b[A-Z]{2,10}\b")
    # Title Case (1 or more capitalized words)
    title_pattern = re.compile(r"\b(?:[A-Z][a-z0-9]+\s?)+\b")
    
    # Pure numbers / versions / years
    pure_numeric = re.compile(r"^\d+$")
    version_numeric = re.compile(r"^(?:v\d+|\d+(?:\.\d+)+)$", re.IGNORECASE)
    
    # Allowed alphanumeric/special identifiers that contain digits
    allowed_alphanumeric = re.compile(
        r"^(?:CVE-\d{4}-\d{4,}|CWE-\d+|SHA\d*|MD5|IPv\d+|OAuth\d+|TLS\d+(?:\.\d+)?|SSLv\d+)$",
        re.IGNORECASE
    )
    
    # Rule IDs, ticket numbers, internal references, generated identifiers (to suppress)
    rule_id_pattern = re.compile(r"^[A-Z]?\d+[A-Z0-9]*$", re.IGNORECASE)
    
    existing_orgs = set(rules_loader.organization_terms)
    existing_acronyms = set(rules_loader.acronyms.keys())
    existing_whitelist = set(rules_loader.spelling_whitelist)
    
    pending_terms = set()
    if hasattr(rules_loader, "learning_queue"):
        for item in rules_loader.learning_queue:
            term_val = item.get("term") or item.get("Candidate Name")
            if term_val:
                pending_terms.add(term_val.lower())
    
    # Initialize spellchecker to filter out common english words for acronyms
    try:
        from spellchecker import SpellChecker
        spell = SpellChecker()
    except ImportError:
        spell = None
    
    # Combine knowledge base words
    vuln_words = set()
    if hasattr(rules_loader, "_vulnerabilities"):
        for v in rules_loader._vulnerabilities:
            for w in v.get("title", "").split():
                vuln_words.add(w.lower())
            for w in v.get("keywords", []):
                vuln_words.add(w.lower())
    
    # Tracking for metadata summary
    raw_candidates_seen = set()
    
    def is_suppressed_and_score(term: str, is_acronym: bool = False, context: str = "") -> Tuple[bool, int]:
        """
        Evaluates filtering rules and returns (is_suppressed, confidence_score).
        """
        term_upper = term.upper()
        term_lower = term.lower()
        
        # Add to raw unique set
        raw_candidates_seen.add(term)
        
        # 1. Repeated-character artifacts check (e.g. ssssystem, ===)
        if re.search(r"(.)\1\1", term):
            return True, 0
            
        # 2. Generic word blocklist
        if term_upper in GENERIC_WORDS:
            return True, 0
            
        # 3. Numeric & Code Filtering
        # If term has digits:
        if re.search(r"\d", term):
            # Allow only explicitly whitelisted patterns like CVE, IPv6
            if not allowed_alphanumeric.match(term):
                return True, 0
        
        # Also catch rule IDs like R00905
        if rule_id_pattern.match(term) and not allowed_alphanumeric.match(term):
            return True, 0

        # 4. Length Constraints
        # Reject candidates shorter than 3 characters unless Acronym
        if len(term) < 3 and not is_acronym:
            return True, 0
            
        # 5. Vowel check (Noise Filtering)
        # Reject tokens with no vowels unless classified as Acronym
        if not is_acronym:
            if not re.search(r"[aeiouy]", term_lower):
                return True, 0
                
        # 6. Dictionary / Whitelist / Vuln DB duplication
        # If the term is already known, we don't need to discover it!
        if term not in branding_orgs:
            if term_lower in existing_whitelist or term_lower in vuln_words or term_lower in existing_orgs:
                return True, 0
            if term_upper in existing_acronyms:
                return True, 0
            
            # Dictionary check for acronyms to avoid common English words (EMAIL, SUMMARY)
            if is_acronym and spell is not None:
                if term_lower in spell:
                    return True, 0
                    
        # 7. Check if already in learning queue
        if term_lower in pending_terms:
            return True, 0

        # Calculate Confidence Score (0 - 100)
        score = 0
        
        # entity weight
        if term in branding_orgs:
            score += 40
        elif term_lower in existing_orgs:
            score += 30
            
        # context keywords
        has_context_kw = False
        if context:
            for kw in ORG_KEYWORDS.union(PRODUCT_KEYWORDS):
                if re.search(rf"\b{kw}\b", context.lower()):
                    has_context_kw = True
                    break
        if has_context_kw:
            score += 25
            
        # dictionary health
        if spell is not None:
            if not is_acronym and term_lower in spell:
                score += 20
                
        return False, score

    # Context window cache
    term_contexts = {}

    for para in paragraphs:
        words = para.split()
        
        # 1. Extract Acronyms
        for i, word in enumerate(words):
            clean_word = word.strip(".,;:()[]{}\"'")
            if not clean_word: continue
            
            if acronym_pattern.fullmatch(clean_word) and not pure_numeric.match(clean_word) and not version_numeric.match(clean_word):
                # Context surrounding acronym
                start_w = max(0, i - 5)
                end_w = min(len(words), i + 6)
                context = " ".join(words[start_w:end_w])
                
                suppressed, base_score = is_suppressed_and_score(clean_word, is_acronym=True, context=context)
                if not suppressed:
                    if clean_word not in candidates:
                        candidates[clean_word] = {"term": clean_word, "type": "Acronyms", "count": 0, "base_score": base_score}
                    candidates[clean_word]["count"] += 1
                    term_contexts[clean_word] = context

        # 2. Extract Title Case candidates
        for match in title_pattern.finditer(para):
            term = match.group().strip()
            if not term: continue
            
            # If it's already processed as acronym, skip
            if term in candidates and candidates[term]["type"] == "Acronyms":
                continue
                
            start_idx = max(0, match.start() - 40)
            end_idx = min(len(para), match.end() + 40)
            context = para[start_idx:end_idx]
            
            suppressed, base_score = is_suppressed_and_score(term, is_acronym=False, context=context)
            if suppressed:
                continue
                
            # Classify type
            candidate_type = "Terms"
            if term in branding_orgs or term.lower() in existing_orgs:
                candidate_type = "Organizations"
            else:
                for kw in ORG_KEYWORDS:
                    if re.search(rf"\b{kw}\b", context.lower()) or re.search(rf"\b{kw}\b", term.lower()):
                        candidate_type = "Organizations"
                        break
            
            if candidate_type == "Terms":
                for kw in PRODUCT_KEYWORDS:
                    if re.search(rf"\b{kw}\b", context.lower()):
                        candidate_type = "Products"
                        break
                parts = term.split()
                if len(parts) >= 2 and parts[0].lower() in existing_orgs:
                    candidate_type = "Products"
                    
            if term not in candidates:
                candidates[term] = {"term": term, "type": candidate_type, "count": 0, "base_score": base_score}
            candidates[term]["count"] += 1
            term_contexts[term] = context

    # Filter, calculate final confidence, and format
    eligible_list = []
    
    for k, v in candidates.items():
        count = v["count"]
        base_score = v["base_score"]
        
        # Calculate final score by adding occurrences weight
        final_score = base_score
        if count >= 5:
            final_score += 50
        elif count >= 3:
            final_score += 30
        else: # count == 2
            final_score += 10
            
        # Determine confidence label
        if final_score >= 60 or count >= 5:
            confidence = "High"
        elif final_score >= 30:
            confidence = "Medium"
        else:
            confidence = "Low"
            
        # Minimum occurrence check
        if count < 2:
            continue
            
        # Quality filter: If confidence is Low and occurrences count is below 3 (i.e. count == 2), suppress!
        if confidence == "Low" and count < 3:
            continue
            
        v["confidence"] = confidence
        del v["base_score"] # Clean up internal temp score
        eligible_list.append(v)

    # Calculate filtered candidates count
    # Filtered is: total unique raw terms seen minus the ones that made it to the final list
    total_found = len(raw_candidates_seen)
    eligible_count = len(eligible_list)
    filtered_count = total_found - eligible_count
    
    # Sort eligible by count descending
    eligible_list.sort(key=lambda x: x["count"], reverse=True)
    eligible_list = eligible_list[:50] # Limit to top 50
    
    summary = {
        "total_found": total_found,
        "filtered_count": filtered_count,
        "eligible_count": len(eligible_list)
    }
    
    return eligible_list, summary
