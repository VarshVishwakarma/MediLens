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
        med_lower = med_name.lower()

        # 🥇 DIRECT MATCH (MOST IMPORTANT)
        if med_lower in text_lower:
            results.append({
                "name": med_name.capitalize(),
                "confidence": 100,
                "level": "high"
            })
            continue

        # 🥈 FUZZY MATCH
        score = fuzz.token_set_ratio(med_lower, text_lower)

        # 🥉 PARTIAL WORD MATCH (handles broken OCR)
        if any(part in text_lower for part in med_lower.split()):
            score = max(score, 85)

        # 🔻 LOWER THRESHOLD
        if score >= 60:
            if score >= 90:
                level = "high"
            elif score >= 75:
                level = "medium"
            else:
                level = "low"

            results.append({
                "name": med_name.capitalize(),
                "confidence": round(score, 2),
                "level": level
            })

    return sorted(results, key=lambda x: x["confidence"], reverse=True)[:3]
