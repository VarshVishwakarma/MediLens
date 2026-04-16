import re
from rapidfuzz import fuzz
from core.loader import get_medicines

def detect_medicines(text: str) -> list:
    if not text:
        return []
        
    # STEP 1 — CLEAN TEXT
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    if not text:
        return []
        
    # STEP 2 — TOKENIZE
    words = set(text.split())
    med_db = get_medicines()
    matches = []
    
    # STEP 3 — MULTI-LAYER MATCHING
    for med_name in med_db:
        med_lower = med_name.lower()
        confidence = 0.0
        
        if med_lower in text:
            confidence = 100.0
        else:
            fuzzy_conf = fuzz.partial_ratio(med_lower, text)
            has_token = any(token in words for token in med_lower.split())
            
            if has_token:
                confidence = max(85.0, fuzzy_conf)
            else:
                confidence = fuzzy_conf
                
        # STEP 4 — DYNAMIC THRESHOLD
        if confidence >= 60:
            if confidence >= 90:
                level = "high"
            elif confidence >= 80:
                level = "medium"
            else:
                level = "low"
                
            matches.append({
                "name": med_name,
                "confidence": round(confidence, 1),
                "level": level
            })
            
    # STEP 5 — LIMIT RESULTS
    matches.sort(key=lambda x: x["confidence"], reverse=True)
    return matches[:3]
