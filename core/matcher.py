from rapidfuzz import fuzz
from core.loader import get_medicines

def detect_medicines(text: str) -> list:
    if not text:
        return []
        
    text = text.lower().strip()
    if not text:
        return []
        
    med_db = get_medicines()
    matches = []
    
    for med_name in med_db:
        med_lower = med_name.lower()
        
        med_len = len(med_lower)
        if med_len <= 5:
            threshold = 75
        elif med_len <= 8:
            threshold = 70
        else:
            threshold = 65
            
        confidence = 0.0
        
        if med_lower in text:
            confidence = 100.0
        else:
            confidence = fuzz.token_set_ratio(med_lower, text)
            
            parts = med_lower.split()
            if len(parts) > 1 and any(part in text for part in parts):
                confidence = min(100.0, confidence + 5.0)
                
        if confidence >= threshold:
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
            
    matches.sort(key=lambda x: x["confidence"], reverse=True)
    return matches[:3]
