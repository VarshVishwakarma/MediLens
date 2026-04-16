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
    
    # STEP 3 — LOAD DATABASE
    med_db = get_medicines()
    matches = []
    
    # STEP 4 — MATCHING LOGIC (CORE)
    for med_name, med_data in med_db.items():
        med_lower = med_name.lower()
        aliases = [alias.lower() for alias in med_data.get("aliases", [])]
        
        confidence = 0.0
        
        # 1. DIRECT MATCH
        if med_lower in text:
            confidence = max(confidence, 100.0)
            
        # 2. ALIAS MATCH
        for alias in aliases:
            if alias in text:
                confidence = max(confidence, 90.0)
                
        # 3. TOKEN MATCH & 4. FUZZY MATCH
        terms_to_check = [med_lower] + aliases
        for term in terms_to_check:
            term_tokens = term.split()
            if any(token in words for token in term_tokens):
                confidence = max(confidence, 85.0)
                
            fuzzy_conf = fuzz.partial_ratio(term, text)
            confidence = max(confidence, fuzzy_conf)
                
        # STEP 5 — CONFIDENCE FILTERING
        if confidence >= 75.0:
            # STEP 6 — ASSIGN LEVEL
            if confidence >= 90.0:
                level = "high"
            elif confidence >= 80.0:
                level = "medium"
            else:
                level = "low"
                
            matches.append({
                "name": med_name,
                "confidence": round(confidence, 1),
                "level": level
            })
            
    # STEP 7 — SORT & LIMIT
    matches.sort(key=lambda x: x["confidence"], reverse=True)
    return matches[:3]
