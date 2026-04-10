import os
import json
import re
import string
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
from thefuzz import fuzz

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_SOURCE = os.path.join(BASE_DIR, "data", "medicines.json")


class OCRService:
    def __init__(self):
        print("[INFO] OCRService initialized")

    def _preprocess(self, img):
        try:
            gray = ImageOps.grayscale(img)
            enhancer = ImageEnhance.Contrast(gray)
            return enhancer.enhance(2.0)
        except:
            return img

    def extract_signals(self, image_file):
        try:
            image_file.seek(0)
            img = Image.open(image_file)

            processed = self._preprocess(img)

            raw_text = pytesseract.image_to_string(
                processed,
                config='--oem 3 --psm 3'
            )

            dosages = re.findall(r'\b\d+\s?(mg|ml|g|mcg)\b', raw_text, re.IGNORECASE)
            frequencies = re.findall(r'\b(OD|BD|TDS|SOS|1-0-1)\b', raw_text, re.IGNORECASE)

            return {
                "raw_text": raw_text.strip(),
                "dosages": list(set(dosages)),
                "frequencies": list(set(frequencies))
            }

        except Exception as e:
            print("❌ OCR Error:", e)
            return {"raw_text": "", "dosages": [], "frequencies": []}


class IdentificationService:
    def __init__(self):
        print("[INFO] IdentificationService initialized")
        self.db = self._load_medicines()

    def _load_medicines(self):
        if not os.path.exists(JSON_SOURCE):
            print("❌ medicines.json not found")
            return {}

        with open(JSON_SOURCE, "r", encoding="utf-8") as f:
            data = json.load(f)

        mapping = {}

        for item in data.get("medicines", []):
            name = item.get("name")
            if not name:
                continue

            mapping[name.lower()] = name

            for alias in item.get("aliases", []):
                mapping[alias.lower()] = name

        return mapping

    def identify(self, text, threshold=70):
        if not text:
            return []

        text = text.lower()
        words = set(text.split())

        results = {}

        for key, value in self.db.items():
            score = 0

            if key in words:
                score = 100
            elif key in text:
                score = 90
            else:
                score = fuzz.partial_ratio(key, text)

            if score >= threshold:
                if value not in results or score > results[value]:
                    results[value] = score

        return [
            {"name": k, "score": v}
            for k, v in sorted(results.items(), key=lambda x: x[1], reverse=True)
        ]


def load_services():
    print("🚀 Loading services...")

    try:
        return {
            "ocr": OCRService(),
            "id": IdentificationService()
        }
    except Exception as e:
        print("❌ Service load error:", e)
        return {"ocr": None, "id": None}
