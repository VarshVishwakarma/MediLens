import os
import json
import re
import string
import pytesseract
from platform_services import load_services
from PIL import Image, ImageOps, ImageEnhance
from thefuzz import fuzz

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_SOURCE = os.path.join(BASE_DIR, "data", "medicines.json")

# Windows Path Fix for Tesseract
if os.name == 'nt':
    default_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.join(os.getenv('LOCALAPPDATA', ''), r"Tesseract-OCR\tesseract.exe")
    ]
    for p in default_paths:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            break


class OCRService:
    """Lightweight OCR service using pytesseract."""
    
    def __init__(self):
        print("[INFO] Initializing OCRService...")

    def _preprocess(self, img):
        """Basic preprocessing: grayscale + contrast enhancement."""
        try:
            gray = ImageOps.grayscale(img)
            enhancer = ImageEnhance.Contrast(gray)
            return enhancer.enhance(2.0)
        except Exception as e:
            print(f"[ERROR] Preprocessing failed: {e}")
            return img

    def extract_signals(self, image_file) -> dict:
        """Extracts raw text, dosages, and frequencies from an image."""
        print("[INFO] Starting OCR extraction...")
        try:
            if hasattr(image_file, 'seek'):
                image_file.seek(0)
            
            img = Image.open(image_file)
            processed_img = self._preprocess(img)
            
            raw_text = pytesseract.image_to_string(processed_img, config=r'--oem 3 --psm 3')
            
            # Signal Extraction RegEx
            dosages = re.findall(r'\b\d+\s?(?:mg|ml|g|mcg)\b', raw_text, re.IGNORECASE)
            frequencies = re.findall(r'\b(?:OD|BD|TDS|BID|QID|SOS|1-0-1|0-1-0|0-0-1)\b', raw_text, re.IGNORECASE)
            
            print("[INFO] OCR extraction completed.")
            return {
                "raw_text": raw_text.strip(),
                "dosages": list(set(dosages)),
                "frequencies": list(set(frequencies))
            }
        except Exception as e:
            print(f"[ERROR] OCR extraction failed: {e}")
            return {
                "raw_text": "",
                "dosages": [],
                "frequencies": []
            }


class IdentificationService:
    """Medicine identification engine using exact, substring, and fuzzy matching."""
    
    def __init__(self):
        print("[INFO] Initializing IdentificationService...")
        self.known_db = self._load_medicines()

    def _load_medicines(self) -> dict:
        """Safely load medicines from local JSON."""
        mapping = {}
        if not os.path.exists(JSON_SOURCE):
            print(f"[WARN] Database file not found at: {JSON_SOURCE}")
            return mapping
            
        try:
            with open(JSON_SOURCE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            for item in data.get("medicines", []):
                canonical = item.get("name")
                if not canonical:
                    continue
                    
                mapping[canonical.lower()] = canonical
                for alias in item.get("aliases", []):
                    mapping[alias.lower()] = canonical
            
            print(f"[INFO] Loaded {len(set(mapping.values()))} unique medicines.")
        except Exception as e:
            print(f"[ERROR] Failed to load medicines JSON: {e}")
            
        return mapping

    def identify(self, text: str, threshold: int = 65) -> list:
        """Identifies medicines from text with a minimum confidence threshold."""
        print("[INFO] Starting identification process...")
        
        if not text or not isinstance(text, str):
            print("[WARN] Empty or invalid text provided.")
            return []

        # Normalize text
        translator = str.maketrans(string.punctuation, ' ' * len(string.punctuation))
        clean_text = text.lower().translate(translator)
        tokens = set(clean_text.split())
        
        candidates = {}

        for key, canonical in self.known_db.items():
            score = 0
            
            # 1. Exact Token Match
            if key in tokens:
                score = 100
            # 2. Substring Match
            elif key in clean_text:
                score = 90
            # 3. Fuzzy Match
            else:
                score = fuzz.partial_ratio(key, clean_text)
            
            # Enforce Threshold
            if score >= threshold:
                if canonical not in candidates or score > candidates[canonical]:
                    candidates[canonical] = score
        
        results = [{"name": k, "score": v} for k, v in candidates.items()]
        results.sort(key=lambda x: x['score'], reverse=True)
        
        print(f"[INFO] Identification completed. Found {len(results)} matches.")
        return results


def load_services() -> dict:
    """Initializes and returns the core MediLens services."""
    print("[INFO] Loading MediLens services...")
    try:
        services = {
            "ocr": OCRService(),
            "id": IdentificationService()
        }
        print("[INFO] Services loaded successfully.")
        return services
    except Exception as e:
        print(f"[ERROR] Failed to initialize services: {e}")
        return {
            "ocr": None,
            "id": None
        }

def load_services():
    print("🚀 Loading services...")

    return {
        "ocr": OCRService(),
        "id": IdentificationService()
    }
