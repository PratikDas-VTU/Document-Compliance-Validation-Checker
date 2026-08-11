"""
branding_engine.py — Logo fingerprint database and hybrid matcher.
Combines pHash and ORB matching to match document images to reference logos.
Tracks telemetry and diagnostic stats.
"""
from __future__ import annotations
import os
import cv2
import numpy as np
import threading
import time
from typing import Dict, Any, List, Tuple

class BrandingEngine:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(BrandingEngine, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self.logo_db: Dict[str, Dict[str, Any]] = {}
        self.status = "Initializing"
        self.loaded_logos_count = 0
        self.loaded_logos_names: List[str] = []
        self.fingerprint_status = "Pending"
        
        # Telemetry & Diagnostics
        self.total_matches_performed = 0
        self.match_success_count = 0
        self.total_images_analyzed = 0
        self.total_mismatches_found = 0
        self.last_matching_duration_ms = 0.0
        
        # Start database loading in a background thread
        threading.Thread(target=self.initialize_engine, daemon=True).start()

    def initialize_engine(self) -> None:
        try:
            self.status = "Initializing"
            self.fingerprint_status = "In Progress"
            
            from app.utils.path_helper import get_logo_repository_path
            logo_dir = get_logo_repository_path()
            
            if not os.path.exists(logo_dir):
                self.status = "Error (Logo Dir Not Found)"
                self.fingerprint_status = "Failed"
                return

            orb = cv2.ORB_create(nfeatures=2000)
            
            logos_found = 0
            logos_names = []
            
            for file_name in os.listdir(logo_dir):
                if file_name.lower().endswith((".png", ".jpg", ".jpeg")):
                    org_name = self._clean_org_name(file_name)
                    file_path = os.path.join(logo_dir, file_name)
                    
                    # Read image
                    img_gray = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
                    if img_gray is not None:
                        # Extract ORB
                        kp, des = orb.detectAndCompute(img_gray, None)
                        
                        # Calculate pHash
                        phash = self._calculate_phash(img_gray)
                        
                        self.logo_db[org_name] = {
                            "descriptors": des,
                            "keypoints_count": len(kp),
                            "phash": phash,
                            "filename": file_name,
                            "raw_name": os.path.splitext(file_name)[0]
                        }
                        logos_found += 1
                        logos_names.append(org_name)
            
            self.loaded_logos_count = logos_found
            self.loaded_logos_names = sorted(logos_names)
            self.status = "Operational"
            self.fingerprint_status = "Completed"
        except Exception as e:
            self.status = f"Error ({str(e)})"
            self.fingerprint_status = "Failed"

    def _clean_org_name(self, filename: str) -> str:
        """Derive a display name from the logo filename using generic word capitalisation."""
        base = os.path.splitext(filename)[0]
        parts = base.replace("_", " ").replace("-", " ").split()
        words = []
        for p in parts:
            p_lower = p.lower()
            # Preserve well-known all-caps abbreviations
            if p_lower in ("tcs", "pwc", "iiit", "iit", "ibm", "hcl"):
                words.append(p.upper())
            else:
                words.append(p.capitalize())
        return " ".join(words)

    def _calculate_phash(self, img_gray: np.ndarray) -> int:
        try:
            # Resize to 32x32
            resized = cv2.resize(img_gray, (32, 32))
            img_float = np.float32(resized)
            dct = cv2.dct(img_float)
            
            # Top-left 8x8 block
            dct_block = dct[0:8, 0:8]
            flat = dct_block.flatten()
            
            # Exclude DC coefficient flat[0]
            mean_val = np.mean(flat[1:])
            
            hash_val = 0
            for idx, val in enumerate(flat):
                if idx == 0:
                    bit = 0
                else:
                    bit = 1 if val > mean_val else 0
                hash_val |= (bit << idx)
            return hash_val
        except Exception:
            return 0

    def match_image(self, img_bytes: bytes) -> Tuple[str | None, float]:
        """
        Match doc image bytes against logo database using hybrid pHash + ORB matcher.
        Returns (Matched Org Name or None, Confidence Score).
        """
        self.total_matches_performed += 1
        
        # Convert bytes to cv2 image
        nparr = np.frombuffer(img_bytes, np.uint8)
        img_gray = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        
        if img_gray is None:
            return None, 0.0
            
        start_time = time.perf_counter()
        
        # Calculate pHash
        hash_doc = self._calculate_phash(img_gray)
        
        # Extract ORB descriptors
        orb = cv2.ORB_create(nfeatures=2000)
        kp_doc, des_doc = orb.detectAndCompute(img_gray, None)
        
        best_org = None
        best_confidence = 0.0
        
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        
        for org_name, ref in self.logo_db.items():
            ref_des = ref["descriptors"]
            ref_kps_count = ref["keypoints_count"]
            hash_ref = ref["phash"]
            
            # pHash similarity
            if hash_doc != 0 and hash_ref != 0:
                xor_hash = hash_doc ^ hash_ref
                hamming_dist = bin(xor_hash).count('1')
                sim_phash = ((64 - hamming_dist) / 64.0) * 100.0
            else:
                sim_phash = 0.0
                
            # ORB match similarity
            if des_doc is not None and ref_des is not None and len(kp_doc) >= 10 and ref_kps_count >= 10:
                try:
                    matches = bf.match(des_doc, ref_des)
                    good_matches = [m for m in matches if m.distance < 40.0]
                    good_count = len(good_matches)
                    
                    # Normalization: match ratio relative to reference logo keypoints
                    orb_ratio = good_count / ref_kps_count if ref_kps_count > 0 else 0.0
                    sim_orb = min(100.0, orb_ratio * 400.0)
                except Exception:
                    good_count = 0
                    sim_orb = 0.0
            else:
                good_count = 0
                sim_orb = 0.0
                
            # False Positive Guard: If ORB has too few good matches, it's not a real logo match
            if good_count < 15 or (des_doc is not None and (good_count / len(des_doc)) < 0.02):
                confidence = 0.0
            else:
                # Hybrid matching formula
                confidence = 0.4 * sim_phash + 0.6 * sim_orb
                
            if confidence > best_confidence:
                best_confidence = confidence
                best_org = org_name
                
        self.last_matching_duration_ms = (time.perf_counter() - start_time) * 1000.0
        
        # If match is high enough to be valid (threshold 45%)
        if best_org and best_confidence >= 40.0:
            self.match_success_count += 1
            return best_org, best_confidence
        return None, 0.0
