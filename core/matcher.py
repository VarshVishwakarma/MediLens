import json
from rapidfuzz import fuzz

def load_medicines():
    try:
        with open("medicines.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

med_db = load_medicines()

def detect_medicines(text: str):
    if not text:
        return []

    text_lower = text.lower().strip()
    if not text_lower:
        return []

    results = []

    for med_name in med_db.keys():
        score = fuzz.token_set_ratio(med_name.lower(), text_lower)
        
        if score >= 70:
            if score >= 90:
                level = "high"
            elif score >= 80:
                level = "medium"
            else:
                level = "low"

            results.append({
                "name": med_name.capitalize(),
                "confidence": round(score, 2),
                "level": level
            })

    return sorted(results, key=lambda x: x["confidence"], reverse=True)[:3]
