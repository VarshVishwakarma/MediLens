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
    for med_name, med_data in med_db.items():
        med_lower = med_name.lower()
        aliases = [alias.lower() for alias in med_data.get("aliases", [])]
        
        confidence = 0.0
        
        # Check direct match for name or aliases
        if med_lower in text or any(alias in text for alias in aliases):
            confidence = 100.0
        else:
            fuzzy_conf = fuzz.partial_ratio(med_lower, text)
            has_token = any(token in words for token in med_lower.split())
            
            # Also check if any tokens of aliases are in words, or if aliases have a fuzzy match
            for alias in aliases:
                alias_fuzzy = fuzz.partial_ratio(alias, text)
                if alias_fuzzy > fuzzy_conf:
                    fuzzy_conf = alias_fuzzy
                if any(token in words for token in alias.split()):
                    has_token = True
            
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
